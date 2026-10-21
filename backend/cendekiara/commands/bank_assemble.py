"""bank.assemble: preview a package with question numbers. Content only, no keys."""

from __future__ import annotations

from cendekiara.core import assemble
from cendekiara.core.assemble import AssembledTest
from cendekiara.core.context import Context
from cendekiara.core.items import Test
from cendekiara.core.models import Model
from cendekiara.core.registry import Command, command


class BankAssembleIn(Model):
    exam: str
    sections: dict[str, list[str]]  # section id -> item ids, in display order
    duration_sec: int | None = None
    free: bool = False
    wrong_penalty: float = 0.0


@command(
    "bank.assemble",
    summary="Preview an assembled package (content only, never keys)",
    admin_only=True,
    readonly=True,
)
class BankAssemble(Command[BankAssembleIn, AssembledTest]):
    def run(self, args: BankAssembleIn, ctx: Context) -> AssembledTest:
        spec = Test(
            id="preview",
            exam=args.exam,
            sections=args.sections,
            duration_sec=args.duration_sec,
            free=args.free,
            wrong_penalty=args.wrong_penalty,
        )
        return assemble.assemble_test(ctx.store, spec)
