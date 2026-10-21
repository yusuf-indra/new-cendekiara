"""attempt.pause: pause a practice attempt."""

from __future__ import annotations

from cendekiara.core.clock import now
from cendekiara.core.context import Context
from cendekiara.core.errors import AppError
from cendekiara.core.models import Model
from cendekiara.core.registry import Command, command


class AttemptPauseIn(Model):
    attempt_id: str


class AttemptPauseOut(Model):
    ok: bool = True
    status: str


@command("attempt.pause", summary="Pause a practice attempt")
class AttemptPause(Command[AttemptPauseIn, AttemptPauseOut]):
    def run(self, args: AttemptPauseIn, ctx: Context) -> AttemptPauseOut:
        uid = ctx.actor.require_uid()
        doc = ctx.store.get("attempts", args.attempt_id)
        if not doc:
            raise AppError("not_found", "attempt not found")
        if doc.get("uid") != uid:
            raise AppError("not_found", "attempt not found")
        if doc.get("status") == "submitted":
            raise AppError("conflict", "attempt already submitted")
        if doc.get("mode") != "practice":
            raise AppError("invalid_args", "only practice attempts can be paused")
        ctx.store.update(
            "attempts",
            args.attempt_id,
            {"status": "paused", "pausedAt": now().isoformat(), "updatedAt": now().isoformat()},
        )
        return AttemptPauseOut(ok=True, status="paused")
