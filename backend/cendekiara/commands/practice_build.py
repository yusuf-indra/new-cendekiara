"""practice.build: build a practice set from the bank.

A practice set never holds an item of an exam package, whatever the status
of that package: an exam item would leak its key through the explanation of
the result (docs/10-security.md, "Exam engine security").

Only the items that are flagged for practice (`usage.practice`) are offered:
an item that is flagged for the exam or for study alone is not a practice
item.

The command returns the package (the ids of the items) and its content, both
built by the server. `attempt.start` rebuilds the content from the ids, so a
client can never smuggle an exam question into a practice attempt.
"""

from __future__ import annotations

import uuid
from typing import Any

from cendekiara.core.assemble import assemble_test
from cendekiara.core.context import Context
from cendekiara.core.errors import AppError
from cendekiara.core.items import Item, Test, exam_package_item_ids
from cendekiara.core.models import Model
from cendekiara.core.registry import Command, command


class PracticeBuildIn(Model):
    exam_id: str | None = None
    section: str | None = None
    sections: list[str] | None = None
    topics: list[str] | None = None
    difficulty: list[int] | None = None
    count: int = 10
    # A practice set has no timer by default; the client may ask for one.
    duration_sec: int | None = None


class PracticeBuildOut(Model):
    package: dict[str, Any]
    content: dict[str, Any]
    item_ids: list[str]


@command("practice.build", summary="Build a practice set from the bank (never an exam item)")
class PracticeBuild(Command[PracticeBuildIn, PracticeBuildOut]):
    def run(self, args: PracticeBuildIn, ctx: Context) -> PracticeBuildOut:
        ctx.actor.require_uid()
        candidates = _candidates(ctx, args)
        picked = _pick(candidates, args.count)
        if not picked:
            raise AppError("not_found", "No item matches this practice set")
        sections = _sections(picked)
        exam_id = args.exam_id or picked[0].exam
        spec = Test(
            id=f"practice-{uuid.uuid4().hex[:8]}",
            exam=exam_id,
            sections={section_id: [item.id for item in items] for section_id, items in sections.items()},
            duration_sec=args.duration_sec,
            free=True,
            status="active",
        )
        package: dict[str, Any] = {"exam": exam_id, "sections": spec.sections}
        if args.duration_sec is not None:
            package["durationSec"] = args.duration_sec
        content = assemble_test(ctx.store, spec).model_dump(by_alias=True)
        return PracticeBuildOut(
            package=package,
            content=content,
            item_ids=[item.id for item in picked],
        )


def _candidates(ctx: Context, args: PracticeBuildIn) -> list[Item]:
    """The active items that may be used for a practice set."""
    used = exam_package_item_ids(ctx.store)
    candidates: list[Item] = []
    for row in ctx.store.list("items", limit=1000):
        try:
            item = Item.from_doc(row)
        except (ValueError, TypeError):
            continue
        if item.status != "active" or item.id in used:
            continue
        if not item.usage.practice:
            # The item is flagged for another mode only: it is not offered.
            continue
        if args.exam_id and item.exam != args.exam_id:
            continue
        if args.section and item.section != args.section:
            continue
        if args.sections and item.section not in args.sections:
            continue
        if args.difficulty and item.difficulty not in args.difficulty:
            continue
        if args.topics and not _has_topic(item, args.topics):
            continue
        candidates.append(item)
    return candidates


def _has_topic(item: Item, topics: list[str]) -> bool:
    """Is one of the groups of the item in one of the topics?"""
    return any(group.topic in topics for group in item.groups if group.topic)


def _pick(candidates: list[Item], count: int) -> list[Item]:
    """Pick the items: from different families first, siblings only fill up."""
    picked: list[Item] = []
    seen: set[str] = set()
    for item in candidates:
        family = item.family_id
        if family and family in seen:
            continue
        picked.append(item)
        if family:
            seen.add(family)
        if len(picked) >= count:
            return picked
    for item in candidates:
        if item in picked:
            continue
        picked.append(item)
        if len(picked) >= count:
            break
    return picked


def _sections(picked: list[Item]) -> dict[str, list[Item]]:
    """The picked items, grouped by section (the order of the sections is kept)."""
    sections: dict[str, list[Item]] = {}
    for item in picked:
        sections.setdefault(item.section, []).append(item)
    return sections
