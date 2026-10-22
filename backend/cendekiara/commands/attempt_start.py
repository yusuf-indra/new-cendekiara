"""attempt.start: start an attempt from a package (exam or practice).

The package is assembled on the server by `core/assemble.py`: the client
never sends the content of a question, only which items a practice set uses
(docs/04-exams.md).
"""

from __future__ import annotations

import uuid
from datetime import timedelta
from typing import Any, Literal

from cendekiara.core import assemble
from cendekiara.core.clock import now
from cendekiara.core.context import Context
from cendekiara.core.errors import AppError
from cendekiara.core.items import Item, Test, exam_package_item_ids
from cendekiara.core.models import Attempt, Model
from cendekiara.core.registry import Command, command


class AttemptStartIn(Model):
    test_id: str | None = None
    mode: Literal["exam", "practice"] = "exam"
    # A practice set: the exam it belongs to and the items of every section.
    # It may carry a `durationSec` (a practice set has no timer by default).
    package: dict[str, Any] | None = None


class AttemptStartOut(Model):
    attempt_id: str
    exam: str | None = None
    mode: str
    status: str
    deadline_at: str | None = None
    duration_sec: int | None = None
    free: bool = False
    wrong_penalty: float = 0.0
    package: dict[str, Any]


@command("attempt.start", summary="Start an attempt from a package (exam or practice)")
class AttemptStart(Command[AttemptStartIn, AttemptStartOut]):
    def run(self, args: AttemptStartIn, ctx: Context) -> AttemptStartOut:
        uid = ctx.actor.require_uid()
        if args.mode == "exam":
            test = _exam_package(ctx, args.test_id)
        else:
            test = _practice_package(ctx, args.package)
        assembled = assemble.assemble_test(ctx.store, test)
        duration = test.duration_sec
        deadline_at = _deadline(duration)
        attempt_id = uuid.uuid4().hex
        started_at = now().isoformat()
        attempt = Attempt(
            id=attempt_id,
            uid=uid,
            mode=args.mode,
            test_id=test.id,
            exam=test.exam,
            package_snapshot=assembled.model_dump(by_alias=True),
            status="in_progress",
            answers={},
            timings={},
            flags=[],
            deadline_at=deadline_at,
            started_at=started_at,
            updated_at=started_at,
            free=test.free,
            wrong_penalty=test.wrong_penalty,
            duration_sec=duration,
        )
        ctx.store.set("attempts", attempt_id, attempt.to_doc())
        ctx.log.info("attempt started: %s (%s, %s)", attempt_id, args.mode, uid)
        return AttemptStartOut(
            attempt_id=attempt_id,
            exam=test.exam,
            mode=args.mode,
            status="in_progress",
            deadline_at=deadline_at,
            duration_sec=duration,
            free=test.free,
            wrong_penalty=test.wrong_penalty,
            package=assembled.model_dump(by_alias=True),
        )


def _exam_package(ctx: Context, test_id: str | None) -> Test:
    """The package of an exam attempt: an active document of `tests/`."""
    if not test_id:
        raise AppError("invalid_args", "testId is required for an exam attempt")
    doc = ctx.store.get("tests", test_id)
    if doc is None:
        raise AppError("not_found", f"tests/{test_id} not found")
    try:
        test = Test.from_doc(doc)
    except (ValueError, TypeError):
        # A malformed package is not a package: it must not reach the assembler.
        raise AppError("not_found", f"tests/{test_id} not found") from None
    if test.status != "active":
        raise AppError("not_found", f"tests/{test_id} not found")
    return test


def _practice_package(ctx: Context, package: dict[str, Any] | None) -> Test:
    """The package of a practice attempt, rebuilt from the bank.

    The client sends only the ids of the items it wants. The server checks
    every id (active item, flagged for practice, and not part of any exam
    package) and assembles the content itself, so a practice attempt can
    never carry an exam question.
    """
    if not package:
        raise AppError("invalid_args", "package is required for a practice attempt")
    exam_id = package.get("exam")
    sections = package.get("sections")
    if not isinstance(exam_id, str) or not isinstance(sections, dict) or not sections:
        raise AppError("invalid_args", "a practice package needs an exam and its sections")
    used = exam_package_item_ids(ctx.store)
    clean: dict[str, list[str]] = {}
    for section_id, item_ids in sections.items():
        if not isinstance(section_id, str) or not isinstance(item_ids, list):
            raise AppError("invalid_args", "a practice package needs a section and its items")
        for item_id in item_ids:
            if not isinstance(item_id, str):
                raise AppError("invalid_args", "a practice package needs item ids")
            if item_id in used:
                # An exam item would leak its key through the explanation.
                raise AppError("invalid_args", "this item is not available for practice")
            if not _is_practice_item(ctx, item_id):
                raise AppError("invalid_args", "this item is not available for practice")
            clean.setdefault(section_id, []).append(item_id)
    duration = package.get("durationSec")
    return Test(
        id=f"practice-{uuid.uuid4().hex[:8]}",
        exam=exam_id,
        sections=clean,
        duration_sec=duration if isinstance(duration, int) and not isinstance(duration, bool) else None,
        free=True,
        wrong_penalty=0.0,
        status="active",
    )


def _is_practice_item(ctx: Context, item_id: str) -> bool:
    """Is the item in the bank, active and flagged for practice?"""
    doc = ctx.store.get("items", item_id)
    if doc is None:
        return False
    try:
        item = Item.from_doc(doc)
    except (ValueError, TypeError):
        return False
    return item.status == "active" and item.usage.practice


def _deadline(duration_sec: int | None) -> str | None:
    """The deadline of the attempt; None when the attempt has no timer."""
    if not duration_sec or duration_sec <= 0:
        return None
    return (now() + timedelta(seconds=duration_sec)).isoformat()
