"""attempt.resume: resume a practice attempt."""

from __future__ import annotations

from cendekiara.core.clock import now
from cendekiara.core.context import Context
from cendekiara.core.errors import AppError
from cendekiara.core.models import Model
from cendekiara.core.registry import Command, command


class AttemptResumeIn(Model):
    attempt_id: str


class AttemptResumeOut(Model):
    ok: bool = True
    status: str


@command("attempt.resume", summary="Resume a practice attempt")
class AttemptResume(Command[AttemptResumeIn, AttemptResumeOut]):
    def run(self, args: AttemptResumeIn, ctx: Context) -> AttemptResumeOut:
        uid = ctx.actor.require_uid()
        doc = ctx.store.get("attempts", args.attempt_id)
        if not doc:
            raise AppError("not_found", "attempt not found")
        if doc.get("uid") != uid:
            raise AppError("not_found", "attempt not found")
        if doc.get("status") == "submitted":
            raise AppError("conflict", "attempt already submitted")
        if doc.get("mode") != "practice":
            raise AppError("invalid_args", "only practice attempts can be resumed")
        if doc.get("status") != "paused":
            raise AppError("invalid_args", "attempt is not paused")
        ctx.store.update(
            "attempts", args.attempt_id, {"status": "in_progress", "updatedAt": now().isoformat()}
        )
        return AttemptResumeOut(ok=True, status="in_progress")
