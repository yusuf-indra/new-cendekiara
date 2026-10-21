"""item.validate: check an item (and optional key) before saving it."""

from __future__ import annotations

from cendekiara.core import items
from cendekiara.core.context import Context
from cendekiara.core.items import Item, ItemKey
from cendekiara.core.models import Model
from cendekiara.core.registry import Command, command


class ItemValidateIn(Model):
    item: Item
    key: ItemKey | None = None


class ItemValidateOut(Model):
    valid: bool
    errors: list[str]


@command("item.validate", summary="Validate an item (and optional key) before saving", admin_only=True)
class ItemValidate(Command[ItemValidateIn, ItemValidateOut]):
    def run(self, args: ItemValidateIn, ctx: Context) -> ItemValidateOut:
        errors = items.validate_item(args.item, args.key, ctx.store)
        return ItemValidateOut(valid=not errors, errors=errors)
