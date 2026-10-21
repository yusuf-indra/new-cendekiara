"""bank.export: dump the bank (items and answer keys) as JSON, in a job result."""

from __future__ import annotations

from pydantic import Field

from cendekiara.core.context import Context
from cendekiara.core.items import Item, ItemKey
from cendekiara.core.models import Model
from cendekiara.core.registry import Command, command

EXPORT_LIMIT = 10000


class BankExportIn(Model):
    exam: str | None = Field(default=None, description="Only export one exam, or all when omitted")


class BankExportOut(Model):
    """The exported bank. Stored in the job result (note the Firestore 1 MB limit)."""

    count: int
    items: list[Item]
    keys: list[ItemKey]


@command(
    "bank.export",
    summary="Export the question bank (with answer keys) as JSON",
    admin_only=True,
    queued=True,
)
class BankExport(Command[BankExportIn, BankExportOut]):
    def run(self, args: BankExportIn, ctx: Context) -> BankExportOut:
        where = {"exam": args.exam} if args.exam else None
        docs = ctx.store.list("items", where, limit=EXPORT_LIMIT)
        item_ids = [doc["id"] for doc in docs if isinstance(doc.get("id"), str)]
        keys: list[ItemKey] = []
        for item_id in item_ids:
            key_doc = ctx.store.get("item_keys", item_id)
            if key_doc is not None:
                keys.append(ItemKey.from_doc(key_doc))
        ctx.log.info("bank exported: %s items", len(item_ids))
        return BankExportOut(count=len(item_ids), items=[Item.from_doc(doc) for doc in docs], keys=keys)
