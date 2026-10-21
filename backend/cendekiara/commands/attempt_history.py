"""attempt.history: user's attempt history."""

from __future__ import annotations

from typing import Any

from cendekiara.core.context import Context
from cendekiara.core.models import Model
from cendekiara.core.registry import Command, command


class AttemptHistoryIn(Model):
    limit: int = 50


class AttemptHistoryOut(Model):
    attempts: list[dict[str, Any]]


@command("attempt.history", summary="List user's attempts", readonly=True)
class AttemptHistory(Command[AttemptHistoryIn, AttemptHistoryOut]):
    def run(self, args: AttemptHistoryIn, ctx: Context) -> AttemptHistoryOut:
        uid = ctx.actor.require_uid()
        rows = ctx.store.list("attempts", limit=1000)
        attempts: list[dict[str, Any]] = []
        for row in rows:
            if row.get("uid") == uid:
                a = dict(row)
                a.pop("packageSnapshot", None)
                a.pop("package_snapshot", None)
                a.pop("answers", None)
                a.pop("timings", None)
                attempts.append(a)
        attempts.sort(key=lambda x: x.get("startedAt") or x.get("started_at") or "", reverse=True)
        return AttemptHistoryOut(attempts=attempts[: args.limit])
