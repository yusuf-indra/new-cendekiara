"""attempt.pause: pause a practice attempt.

Only a practice attempt can be paused (an exam runs until the deadline), and
only its owner may pause it (docs/04-exams.md, modes).
"""

from __future__ import annotations

from cendekiara.core.attempts import own_attempt
from cendekiara.core.clock import now
from cendekiara.core.context import Context
from cendekiara.core.errors import AppError
from cendekiara.core.models import Model
from cendekiara.core.registry import Command, command


class AttemptPauseIn(Model):
    attempt_id: str


class AttemptPauseOut(Model):
    attempt_id: str
    status: str


@command("attempt.pause", summary="Pause a practice attempt")
class AttemptPause(Command[AttemptPauseIn, AttemptPauseOut]):
    def run(self, args: AttemptPauseIn, ctx: Context) -> AttemptPauseOut:
        uid = ctx.actor.require_uid()
        attempt = own_attempt(ctx.store, args.attempt_id, uid)
        if attempt.status == "submitted":
            raise AppError("conflict", "This attempt is already submitted")
        if attempt.mode != "practice":
            raise AppError("invalid_args", "Only a practice attempt can be paused")
        if attempt.status == "paused":
            raise AppError("conflict", "This attempt is already paused")
        paused_at = now().isoformat()
        ctx.store.update(
            "attempts",
            args.attempt_id,
            {"status": "paused", "pausedAt": paused_at, "updatedAt": paused_at},
        )
        return AttemptPauseOut(attempt_id=args.attempt_id, status="paused")
