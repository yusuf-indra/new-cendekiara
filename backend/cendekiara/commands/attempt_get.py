"""attempt.get: get an attempt."""

from __future__ import annotations

from typing import Any

from cendekiara.core.context import Context
from cendekiara.core.errors import AppError
from cendekiara.core.models import Model
from cendekiara.core.registry import Command, command


class AttemptGetIn(Model):
    attempt_id: str


class AttemptGetOut(Model):
    attempt: dict[str, Any]


@command("attempt.get", summary="Get an attempt")
class AttemptGet(Command[AttemptGetIn, AttemptGetOut]):
    def run(self, args: AttemptGetIn, ctx: Context) -> AttemptGetOut:
        uid = ctx.actor.uid
        doc = ctx.store.get("attempts", args.attempt_id)
        if not doc:
            raise AppError("not_found", "attempt not found")
        # ownership check
        if doc.get("uid") != uid and not ctx.actor.is_admin:
            raise AppError("not_found", "attempt not found")
        if ctx.actor.is_admin and doc.get("uid") != uid:
            ctx.log.info("admin read attempt %s by %s", args.attempt_id, uid)
        # never return keys/explanations/transcripts/aiCheck
        attempt = dict(doc)
        # strip any key info if present
        attempt.pop("itemKeys", None)
        attempt.pop("keys", None)
        # ensure no key values leaked
        return AttemptGetOut(attempt=attempt)
