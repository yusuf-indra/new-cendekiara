"""attempt.save: store the answers, the timings and the flags of an attempt.

Only the owner may save. The server decides the time: a save after the
deadline + grace is refused (docs/10-security.md, "Exam engine security").

The answers, the timings and the flags are keyed by the number of the
question (the number the assembly gave it). An answer for a question that is
not in the package is refused; a flag for an unknown question is dropped.
"""

from __future__ import annotations

import json
from typing import Any

from cendekiara.core import config, rate_limit
from cendekiara.core.attempts import (
    Question,
    cap_timings,
    is_past_deadline,
    normalize_answer,
    own_attempt,
    questions_of,
)
from cendekiara.core.clock import now
from cendekiara.core.context import Context
from cendekiara.core.errors import AppError
from cendekiara.core.models import Attempt, Model
from cendekiara.core.registry import Command, command


class AttemptSaveIn(Model):
    attempt_id: str
    answers: dict[str, Any] | None = None
    timings: dict[str, Any] | None = None
    flags: list[str] | None = None


class AttemptSaveOut(Model):
    attempt_id: str
    status: str
    updated_at: str
    saved_answers: int = 0


@command("attempt.save", summary="Save the answers, timings and flags of an attempt")
class AttemptSave(Command[AttemptSaveIn, AttemptSaveOut]):
    def run(self, args: AttemptSaveIn, ctx: Context) -> AttemptSaveOut:
        uid = ctx.actor.require_uid()
        settings = ctx.settings or config.settings
        attempt = own_attempt(ctx.store, args.attempt_id, uid)
        if attempt.status == "submitted":
            raise AppError("conflict", "This attempt is already submitted")
        if attempt.status == "paused":
            raise AppError("conflict", "This attempt is paused")
        _check_limits(args, uid, settings)
        if is_past_deadline(attempt, settings.submit_grace_sec):
            raise AppError("deadline_passed", "The time of this attempt is over")
        questions = questions_of(attempt)
        answers = _merge_answers(attempt, args.answers, questions)
        timings = _merge_timings(attempt, args.timings, questions)
        flags = _flags(attempt, args.flags, questions)
        updated_at = now().isoformat()
        ctx.store.update(
            "attempts",
            args.attempt_id,
            {"answers": answers, "timings": timings, "flags": flags, "updatedAt": updated_at},
        )
        return AttemptSaveOut(
            attempt_id=args.attempt_id,
            status="in_progress",
            updated_at=updated_at,
            saved_answers=len(answers),
        )


def _check_limits(args: AttemptSaveIn, uid: str, settings: config.Settings) -> None:
    """The rate limit and the size limit of a save."""
    payload = json.dumps(
        {"answers": args.answers, "timings": args.timings, "flags": args.flags}, ensure_ascii=False
    )
    if len(payload.encode("utf-8")) > settings.attempt_save_max_bytes:
        raise AppError("invalid_args", "This answer is too large")
    if not rate_limit.limiter.allow(uid, "attempt.save", settings.attempt_save_rate_limit):
        raise AppError("rate_limited", "Too many saves, wait a moment")


def _merge_answers(
    attempt: Attempt,
    answers: dict[str, Any] | None,
    questions: dict[str, Question],
) -> dict[str, Any]:
    """Merge the answers per question: a save never removes an earlier answer."""
    merged = dict(attempt.answers)
    for number, answer in (answers or {}).items():
        question = questions.get(number)
        if question is None:
            raise AppError("invalid_args", f"Unknown question {number!r}")
        merged[number] = normalize_answer(question.group_type, answer)
    return merged


def _merge_timings(
    attempt: Attempt,
    timings: dict[str, Any] | None,
    questions: dict[str, Question],
) -> dict[str, float]:
    """Merge the timings per question, each capped at 3 h by the server."""
    merged = dict(attempt.timings)
    merged.update(cap_timings(timings or {}))
    return {number: seconds for number, seconds in merged.items() if number in questions}


def _flags(attempt: Attempt, flags: list[str] | None, questions: dict[str, Question]) -> list[str]:
    """The flags of the attempt: the list is replaced, and unknown ones are dropped."""
    wanted = list(flags) if flags is not None else list(attempt.flags)
    return [number for number in wanted if number in questions]
