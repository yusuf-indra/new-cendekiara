"""attempt.resume: resume a paused practice attempt.

Only the owner may resume, and only a paused practice attempt can be resumed
(docs/04-exams.md, modes).
"""

from __future__ import annotations

from cendekiara.core.attempts import own_attempt
from cendekiara.core.clock import now
from cendekiara.core.context import Context
from cendekiara.core.errors import AppError
from cendekiara.core.models import Model
from cendekiara.core.registry import Command, command


class AttemptResumeIn(Model):
    attempt_id: str


class AttemptResumeOut(Model):
    attempt_id: str
    status: str


@command("attempt.resume", summary="Resume a paused practice attempt")
class AttemptResume(Command[AttemptResumeIn, AttemptResumeOut]):
    def run(self, args: AttemptResumeIn, ctx: Context) -> AttemptResumeOut:
        uid = ctx.actor.require_uid()
        attempt = own_attempt(ctx.store, args.attempt_id, uid)
        if attempt.status == "submitted":
            raise AppError("conflict", "This attempt is already submitted")
        if attempt.mode != "practice":
            raise AppError("invalid_args", "Only a practice attempt can be resumed")
        if attempt.status != "paused":
            raise AppError("conflict", "This attempt is not paused")
        updated_at = now().isoformat()
        ctx.store.update(
            "attempts",
            args.attempt_id,
            {"status": "in_progress", "pausedAt": None, "updatedAt": updated_at},
        )
        return AttemptResumeOut(attempt_id=args.attempt_id, status="in_progress")
