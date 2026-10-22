"""practice.build: build a practice package from the bank."""

from __future__ import annotations

from typing import Any

from cendekiara.core.context import Context
from cendekiara.core.items import Item, Test
from cendekiara.core.models import Model
from cendekiara.core.registry import Command, command


class PracticeBuildIn(Model):
    exam_id: str | None = None
    section: str | None = None
    sections: list[str] | None = None
    topics: list[str] | None = None
    difficulty: list[int] | None = None
    count: int = 10
    timer: bool = False
    duration_sec: int | None = None


class PracticeBuildOut(Model):
    package: dict[str, Any]
    items: list[dict[str, Any]] | None = None


def _items_in_any_test(store: Any) -> set[str]:
    used = set()
    try:
        tests = store.list("tests", limit=10000)
        for t in tests:
            try:
                test = Test.from_doc(t)
                for _, item_ids in test.sections.items():
                    for iid in item_ids:
                        used.add(iid)
            except (ValueError, TypeError):
                continue
    except (ValueError, TypeError):
        pass
    return used


@command("practice.build", summary="Build a practice package from the bank")
class PracticeBuild(Command[PracticeBuildIn, PracticeBuildOut]):
    def run(self, args: PracticeBuildIn, ctx: Context) -> PracticeBuildOut:
        ctx.actor.require_uid()  # requires login
        used = _items_in_any_test(ctx.store)
        rows = ctx.store.list("items", limit=10000)
        candidates = []
        for row in rows:
            try:
                item = Item.from_doc(row)
            except (ValueError, TypeError):
                continue
            if item.status != "active":
                continue
            if item.id in used:
                continue  # exam-package items never appear in practice
            if args.exam_id and item.exam != args.exam_id:
                continue
            if args.section and item.section != args.section:
                continue
            if args.sections and item.section not in args.sections:
                continue
            if args.topics:
                # check if any group topic in topics
                has_topic = False
                for g in item.groups:
                    if g.topic and g.topic in args.topics:
                        has_topic = True
                if not has_topic:
                    continue
            if args.difficulty and item.difficulty not in args.difficulty:
                continue
            candidates.append(item)
        # pick items from different families first
        picked = []
        seen_families = set()
        # first pass: different families
        for it in candidates:
            fid = it.family_id
            if fid and fid in seen_families:
                continue
            picked.append(it)
            if fid:
                seen_families.add(fid)
            if len(picked) >= args.count:
                break
        # second pass fill
        if len(picked) < args.count:
            for it in candidates:
                if it in picked:
                    continue
                picked.append(it)
                if len(picked) >= args.count:
                    break
        picked = picked[: args.count]
        sections_by_sec: dict[str, list[Item]] = {}
        for it in picked:
            sections_by_sec.setdefault(it.section, []).append(it)
        qnum = 1
        from cendekiara.core.assemble import (
            AssembledGroup,
            AssembledItem,
            AssembledQuestion,
            AssembledSection,
            AssembledTest,
        )

        all_sections: list[AssembledSection] = []
        for sec_id, items in sections_by_sec.items():
            ass_items: list[AssembledItem] = []
            for item in items:
                groups: list[AssembledGroup] = []
                for group in item.groups:
                    questions: list[AssembledQuestion] = []
                    for q in group.questions:
                        questions.append(
                            AssembledQuestion(
                                number=qnum,
                                id=q.id,
                                prompt=q.prompt,
                                options=q.options if q.options is not None else group.options,
                                max_words=q.max_words,
                            )
                        )
                        qnum += 1
                    groups.append(
                        AssembledGroup(
                            id=group.id,
                            type=group.type,
                            topic=group.topic,
                            instructions=group.instructions,
                            questions=questions,
                        )
                    )
                ass_items.append(AssembledItem(id=item.id, stimulus=item.stimulus, groups=groups))
            all_sections.append(AssembledSection(id=sec_id, items=ass_items))
        exam_id = args.exam_id or (picked[0].exam if picked else None) or "tpa-bappenas"
        pkg = AssembledTest(
            exam=exam_id,
            duration_sec=args.duration_sec if args.duration_sec is not None else None,
            free=True,
            wrong_penalty=0.0,
            sections=all_sections,
        )
        package = pkg.model_dump(by_alias=True)
        return PracticeBuildOut(package=package)
