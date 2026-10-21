"""item.update: full replace of an item, and optionally its answer key."""

from __future__ import annotations

from cendekiara.core import clock, items, store
from cendekiara.core.context import Context
from cendekiara.core.errors import AppError
from cendekiara.core.items import Item, ItemKey
from cendekiara.core.models import Model
from cendekiara.core.registry import Command, command


class ItemUpdateIn(Model):
    item: Item
    key: ItemKey | None = None


class ItemUpdateOut(Model):
    id: str
    status: str


@command("item.update", summary="Replace an item (and optionally its key)", admin_only=True)
class ItemUpdate(Command[ItemUpdateIn, ItemUpdateOut]):
    def run(self, args: ItemUpdateIn, ctx: Context) -> ItemUpdateOut:
        existing = ctx.store.get("items", args.item.id)
        if existing is None:
            raise AppError("not_found", f"items/{args.item.id} not found")
        errors = items.validate_item(args.item, args.key, ctx.store)
        if errors:
            raise AppError("invalid_args", "; ".join(errors))
        item = args.item
        item.updated_at = clock.now_iso()
        if item.created_at is None:
            previous = existing.get("createdAt")
            item.created_at = previous if isinstance(previous, str) else item.updated_at
        store.save(ctx.store, "items", item.id, item)
        if args.key is not None:
            store.save(ctx.store, "item_keys", item.id, args.key)
        ctx.log.info("item updated: %s", item.id)
        return ItemUpdateOut(id=item.id, status=item.status)
