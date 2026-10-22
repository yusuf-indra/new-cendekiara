"""attempt.get: read one attempt.

The owner may read their own attempt; an admin may read any attempt to help
a student, and the read is logged with the acting uid. An admin may not
change another user's attempt (docs/10-security.md, "Exam engine security").
"""

from __future__ import annotations

from typing import Any

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
        return AttemptGetOut(attempt=attempt.to_doc())
