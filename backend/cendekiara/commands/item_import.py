"""item.import: import items from JSON. Dry run by default; otherwise save valid ones."""

from __future__ import annotations

from typing import Any

from pydantic import Field, ValidationError

from cendekiara.core import clock, items, store
from cendekiara.core.context import Context
from cendekiara.core.items import Item, ItemKey
from cendekiara.core.models import Model
from cendekiara.core.registry import Command, command


class ItemImportIn(Model):
    items: list[dict[str, Any]] = Field(description="Raw item objects, one per question unit")
    keys: dict[str, dict[str, Any]] | None = Field(default=None, description="Key by item id")
    dry_run: bool = True


class ItemImportReport(Model):
    """The outcome of one item; never contains answer-key content."""

    id: str | None = None
    ok: bool
    saved: bool = False
    errors: list[str] = Field(default_factory=list)


class ItemImportOut(Model):
    dry_run: bool
    total: int
    valid: int
    invalid: int
    saved: int
    reports: list[ItemImportReport]


@command("item.import", summary="Import items from JSON (dry run by default)", admin_only=True, queued=True)
class ItemImport(Command[ItemImportIn, ItemImportOut]):
    def run(self, args: ItemImportIn, ctx: Context) -> ItemImportOut:
        reports: list[ItemImportReport] = []
        valid = invalid = saved = 0
        for raw in args.items:
            report = self._import_one(raw, args.keys, args.dry_run, ctx)
            reports.append(report)
            if report.ok:
                valid += 1
                if report.saved:
                    saved += 1
            else:
                invalid += 1
        return ItemImportOut(
            dry_run=args.dry_run,
            total=len(args.items),
            valid=valid,
            invalid=invalid,
            saved=saved,
            reports=reports,
        )

    def _import_one(
        self,
        raw: dict[str, Any],
        keys: dict[str, dict[str, Any]] | None,
        dry_run: bool,
        ctx: Context,
    ) -> ItemImportReport:
        item_id = raw.get("id") if isinstance(raw, dict) else None
        if not isinstance(item_id, str) or not item_id:
            return ItemImportReport(ok=False, errors=["item has no id"])
        try:
            item = Item.model_validate(raw)
        except ValidationError:
            return ItemImportReport(id=item_id, ok=False, errors=["item is not valid"])
        key: ItemKey | None = None
        key_raw = (keys or {}).get(item_id)
        if key_raw is not None:
            try:
                key = ItemKey.model_validate({**key_raw, "id": item_id})
            except ValidationError:
                return ItemImportReport(id=item_id, ok=False, errors=["item key is not valid"])
        errors = items.validate_item(item, key, ctx.store)
        if errors:
            return ItemImportReport(id=item_id, ok=False, errors=errors)
        if dry_run:
            return ItemImportReport(id=item_id, ok=True, saved=False)
        previous = ctx.store.get("items", item_id)
        previous_created = previous.get("createdAt") if previous else None
        now = clock.now_iso()
        item.updated_at = now
        item.created_at = previous_created if isinstance(previous_created, str) else now
        store.save(ctx.store, "items", item_id, item)
        if key is not None:
            store.save(ctx.store, "item_keys", item_id, key)
        return ItemImportReport(id=item_id, ok=True, saved=True)
