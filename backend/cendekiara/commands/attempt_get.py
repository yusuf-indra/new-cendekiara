"""attempt.get: read one attempt.

The owner may read their own attempt; an admin may read any attempt to help
a student, and the read is logged with the acting uid. An admin may not
change another user's attempt (docs/10-security.md, "Exam engine security").

The owner also gets the result of an attempt that ran out of time: an
attempt past its deadline + the grace is submitted (late) when it is read, so
a student never sees an attempt that stays in progress for ever.
"""

from __future__ import annotations

from typing import Any

from cendekiara.core import config
from cendekiara.core.attempts import submit_if_late
from cendekiara.core.context import Context
from cendekiara.core.errors import AppError
from cendekiara.core.models import Attempt, Model
from cendekiara.core.registry import Command, command


class AttemptGetIn(Model):
    attempt_id: str


class AttemptGetOut(Model):
    attempt: dict[str, Any]


@command("attempt.get", summary="Read one attempt (an admin may read any attempt)", readonly=True)
class AttemptGet(Command[AttemptGetIn, AttemptGetOut]):
    def run(self, args: AttemptGetIn, ctx: Context) -> AttemptGetOut:
        settings = ctx.settings or config.settings
        doc = ctx.store.get("attempts", args.attempt_id)
        if doc is None:
            raise AppError("not_found", "attempt not found")
        owner = doc.get("uid")
        if owner != ctx.actor.uid:
            if not ctx.actor.is_admin:
                # Not the owner: the attempt does not exist for this student.
                raise AppError("not_found", "attempt not found")
            ctx.log.info("admin read attempt %s (owner %s) by %s", args.attempt_id, owner, ctx.actor.uid)
        try:
            attempt = Attempt.from_doc(doc)
        except (ValueError, TypeError) as exc:
            raise AppError("not_found", "attempt not found") from exc
        if owner == ctx.actor.uid:
            # The time of the attempt is over: the owner gets the result of
            # the answers that were saved in time.
            attempt = submit_if_late(ctx.store, attempt, settings.submit_grace_sec)
        return AttemptGetOut(attempt=attempt.to_doc())
