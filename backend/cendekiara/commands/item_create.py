"""item.create: save a new item, and optionally its answer key."""

from __future__ import annotations

from cendekiara.core import clock, items, store
from cendekiara.core.context import Context
from cendekiara.core.errors import AppError
from cendekiara.core.items import Item, ItemKey
from cendekiara.core.models import Model
from cendekiara.core.registry import Command, command


class ItemCreateIn(Model):
    item: Item
    key: ItemKey | None = None


class ItemCreateOut(Model):
    id: str
    status: str


@command("item.create", summary="Create an item (and optionally its answer key)", admin_only=True)
class ItemCreate(Command[ItemCreateIn, ItemCreateOut]):
    def run(self, args: ItemCreateIn, ctx: Context) -> ItemCreateOut:
        errors = items.validate_item(args.item, args.key, ctx.store)
        if errors:
            raise AppError("invalid_args", "; ".join(errors))
        if ctx.store.get("items", args.item.id) is not None:
            raise AppError("conflict", f"items/{args.item.id} already exists")
        item = args.item
        now = clock.now_iso()
        item.updated_at = now
        if item.created_at is None:
            item.created_at = now
        store.save(ctx.store, "items", item.id, item)
        if args.key is not None:
            store.save(ctx.store, "item_keys", item.id, args.key)
        ctx.log.info("item created: %s", item.id)
        return ItemCreateOut(id=item.id, status=item.status)
