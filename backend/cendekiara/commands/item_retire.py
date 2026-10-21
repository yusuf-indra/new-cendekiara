"""item.retire: retire a single item so it stops appearing outside admin."""

from __future__ import annotations

from pydantic import Field

from cendekiara.core import clock
from cendekiara.core.context import Context
from cendekiara.core.errors import AppError
from cendekiara.core.models import Model
from cendekiara.core.registry import Command, command


class ItemRetireIn(Model):
    item_id: str = Field(description="The id of the item to retire")


class ItemRetireOut(Model):
    id: str
    status: str


@command("item.retire", summary="Retire a single item", admin_only=True, allow_jobs=True)
class ItemRetire(Command[ItemRetireIn, ItemRetireOut]):
    def run(self, args: ItemRetireIn, ctx: Context) -> ItemRetireOut:
        if ctx.store.get("items", args.item_id) is None:
            raise AppError("not_found", f"items/{args.item_id} not found")
        ctx.store.update("items", args.item_id, {"status": "retired", "updatedAt": clock.now_iso()})
        ctx.log.info("item retired: %s", args.item_id)
        return ItemRetireOut(id=args.item_id, status="retired")
