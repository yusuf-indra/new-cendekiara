"""study.next: the next item to study.

Study only shows items that are in no exam package: an exam item would leak
its key through the check of the answer (docs/10-security.md, rule 1 and the
"Exam engine security" section).
"""

from __future__ import annotations

from typing import Any

from cendekiara.core.context import Context
from cendekiara.core.items import Item, exam_package_item_ids
from cendekiara.core.models import Model
from cendekiara.core.registry import Command, command


class StudyNextIn(Model):
    exam_id: str | None = None
    section: str | None = None


class StudyNextOut(Model):
    item: dict[str, Any] | None = None


@command("study.next", summary="The next study item (never an exam item)", readonly=True)
class StudyNext(Command[StudyNextIn, StudyNextOut]):
    def run(self, args: StudyNextIn, ctx: Context) -> StudyNextOut:
        ctx.actor.require_uid()
        used = exam_package_item_ids(ctx.store)
        for row in ctx.store.list("items", limit=1000):
            try:
                item = Item.from_doc(row)
            except (ValueError, TypeError):
                continue
            if item.status != "active" or item.id in used or not item.usage.study:
                continue
            if args.exam_id and item.exam != args.exam_id:
                continue
            if args.section and item.section != args.section:
                continue
            return StudyNextOut(item=item.model_dump(by_alias=True))
        return StudyNextOut(item=None)
