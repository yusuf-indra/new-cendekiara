"""attempt.history: the attempts of the signed-in student.

The history holds no answers and no timings: only what the student needs to
recognise an attempt (docs/10-security.md, "Exam engine security").
"""

from __future__ import annotations

from typing import Any

from cendekiara.core.context import Context
from cendekiara.core.models import Attempt, Model
from cendekiara.core.registry import Command, command


class AttemptHistoryIn(Model):
    limit: int = 50


class AttemptHistoryOut(Model):
    attempts: list[dict[str, Any]]


@command("attempt.history", summary="The attempts of the signed-in student", readonly=True)
class AttemptHistory(Command[AttemptHistoryIn, AttemptHistoryOut]):
    def run(self, args: AttemptHistoryIn, ctx: Context) -> AttemptHistoryOut:
        uid = ctx.actor.require_uid()
        attempts: list[dict[str, Any]] = []
        for row in ctx.store.list("attempts", limit=1000):
            if row.get("uid") != uid:
                continue
            try:
                attempt = Attempt.from_doc(row)
            except (ValueError, TypeError):
                continue
            attempts.append(_summary(attempt))
        attempts.sort(key=lambda row: str(row.get("startedAt") or ""), reverse=True)
        return AttemptHistoryOut(attempts=attempts[: args.limit])


def _summary(attempt: Attempt) -> dict[str, Any]:
    """The attempt without its answers, its timings and its package."""
    result = attempt.result
    return {
        "id": attempt.id,
        "mode": attempt.mode,
        "testId": attempt.test_id,
        "exam": attempt.exam,
        "status": attempt.status,
        "score": result.score if result else None,
        "scoreType": result.score_type if result else None,
        "correct": result.correct if result else 0,
        "wrong": result.wrong if result else 0,
        "blank": result.blank if result else 0,
        "startedAt": attempt.started_at,
        "submittedAt": attempt.submitted_at,
        "durationSec": attempt.duration_sec,
        "free": attempt.free,
    }
