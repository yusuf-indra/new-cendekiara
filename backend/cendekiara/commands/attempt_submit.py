"""attempt.submit: submit an attempt and grade the answers that were stored.

The command never accepts final answers: it grades the answers `attempt.save`
stored, so a client cannot send a better answer at the last moment. It may
carry the last timings, which are stored but never change the score
(docs/10-security.md, "Exam engine security").

The owner may always submit: a student who runs out of time still gets a
result. A submit past the deadline + the grace is `late`: it grades the
answers that were saved in time and ignores the timings that come with it.
"""

from __future__ import annotations

from typing import Any

from cendekiara.core import config
from cendekiara.core.attempts import is_past_deadline, own_attempt, submit_attempt
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
        late = is_past_deadline(attempt, settings.submit_grace_sec)
        _, result = submit_attempt(ctx.store, attempt, late=late, timings=args.timings)
        ctx.log.info("attempt submitted: %s (%s, late=%s)", args.attempt_id, uid, late)
        return AttemptSubmitOut(
            attempt_id=args.attempt_id,
            status="submitted",
            result=result.model_dump(by_alias=True),
        )
