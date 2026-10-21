"""study.next: get next study item."""

from __future__ import annotations

from typing import Any

from cendekiara.core.context import Context
from cendekiara.core.items import Item, Test
from cendekiara.core.models import Model
from cendekiara.core.registry import Command, command


class StudyNextIn(Model):
    exam_id: str | None = None
    section: str | None = None


class StudyNextOut(Model):
    item: dict[str, Any] | None = None


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
            except Exception:
                continue
    except Exception:
        pass
    return used


@command("study.next", summary="Get next study item", readonly=True)
class StudyNext(Command[StudyNextIn, StudyNextOut]):
    def run(self, args: StudyNextIn, ctx: Context) -> StudyNextOut:
        ctx.actor.require_uid()
        used = _items_in_any_test(ctx.store)
        rows = ctx.store.list("items", limit=10000)
        for row in rows:
            try:
                item = Item.from_doc(row)
            except Exception:
                continue
            if item.status != "active":
                continue
            if item.id in used:
                continue  # not in any exam package
            if not item.usage.study:
                continue
            if args.exam_id and item.exam != args.exam_id:
                continue
            if args.section and item.section != args.section:
                continue
            # return item without keys
            return StudyNextOut(item=item.model_dump(by_alias=True))
        return StudyNextOut(item=None)
