"""attempt.submit: submit an attempt and grade the answers that were stored.

The command never accepts final answers: it grades the answers `attempt.save`
stored, so a client cannot send a better answer at the last moment. It may
carry the last timings, which are stored but never change the score
(docs/10-security.md, "Exam engine security").
"""

from __future__ import annotations

from typing import Any

from cendekiara.core import config
from cendekiara.core.attempts import cap_timings, grade_attempt, is_past_deadline, own_attempt, questions_of
from cendekiara.core.clock import now
from cendekiara.core.context import Context
from cendekiara.core.errors import AppError
from cendekiara.core.models import Model
from cendekiara.core.registry import Command, command


class AttemptSubmitIn(Model):
    attempt_id: str
    timings: dict[str, Any] | None = None


class AttemptSubmitOut(Model):
    attempt_id: str
    status: str
    result: dict[str, Any]


@command("attempt.submit", summary="Submit an attempt and grade the stored answers")
class AttemptSubmit(Command[AttemptSubmitIn, AttemptSubmitOut]):
    def run(self, args: AttemptSubmitIn, ctx: Context) -> AttemptSubmitOut:
        uid = ctx.actor.require_uid()
        settings = ctx.settings or config.settings
        attempt = own_attempt(ctx.store, args.attempt_id, uid)
        if attempt.status == "submitted":
            raise AppError("conflict", "This attempt is already submitted")
        if is_past_deadline(attempt, settings.submit_grace_sec):
            raise AppError("deadline_passed", "The time of this attempt is over")
        result = grade_attempt(ctx.store, attempt)
        submitted_at = now().isoformat()
        update: dict[str, Any] = {
            "status": "submitted",
            "submittedAt": submitted_at,
            "updatedAt": submitted_at,
            "result": result.model_dump(by_alias=True),
        }
        if args.timings:
            questions = questions_of(attempt)
            timings = dict(attempt.timings)
            timings.update(cap_timings(args.timings))
            update["timings"] = {
                number: seconds for number, seconds in timings.items() if number in questions
            }
        ctx.store.update("attempts", args.attempt_id, update)
        ctx.log.info("attempt submitted: %s (%s)", args.attempt_id, uid)
        return AttemptSubmitOut(
            attempt_id=args.attempt_id,
            status="submitted",
            result=result.model_dump(by_alias=True),
        )
