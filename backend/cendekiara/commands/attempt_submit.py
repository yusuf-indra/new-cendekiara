"""attempt.submit: submit and grade."""

from __future__ import annotations

from typing import Any

from cendekiara.core.attempts import cap_timings, get_submit_grace_sec, grade_attempt
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


@command("attempt.submit", summary="Submit an attempt for grading")
class AttemptSubmit(Command[AttemptSubmitIn, AttemptSubmitOut]):
    def run(self, args: AttemptSubmitIn, ctx: Context) -> AttemptSubmitOut:
        uid = ctx.actor.require_uid()
        doc = ctx.store.get("attempts", args.attempt_id)
        if not doc:
            raise AppError("not_found", "attempt not found")
        if doc.get("uid") != uid:
            raise AppError("not_found", "attempt not found")
        if doc.get("status") == "submitted":
            raise AppError("conflict", "attempt already submitted")
        updates: dict[str, Any] = {}
        if args.timings:
            timings = dict(doc.get("timings") or {})
            for k, v in args.timings.items():
                try:
                    timings[k] = float(v)
                except (TypeError, ValueError):
                    continue
            timings = cap_timings(timings)
            updates["timings"] = timings
        deadline_at = doc.get("deadlineAt") or doc.get("deadline_at")
        if deadline_at:
            try:
                from datetime import datetime, timedelta

                try:
                    dld = datetime.fromisoformat(str(deadline_at).replace("Z", "+00:00"))
                except (TypeError, ValueError):
                    dld = None
                if dld is not None:
                    now_t = now()
                    grace = get_submit_grace_sec(ctx.settings)
                    if now_t > dld + timedelta(seconds=grace):
                        raise AppError("deadline_passed", "deadline passed")
            except AppError:
                raise
            except (TypeError, ValueError):
                pass
        result = grade_attempt(ctx.store, doc, doc.get("packageSnapshot") or doc.get("package_snapshot"))
        updates["status"] = "submitted"
        updates["submittedAt"] = now().isoformat()
        updates["updatedAt"] = now().isoformat()
        updates["result"] = result
        ctx.store.update("attempts", args.attempt_id, updates)
        return AttemptSubmitOut(attempt_id=args.attempt_id, status="submitted", result=result)
