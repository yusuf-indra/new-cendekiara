"""attempt.save: save answers/timings/flags."""

from __future__ import annotations

import json
from typing import Any

from cendekiara.core import rate_limit
from cendekiara.core.attempts import cap_timings, get_submit_grace_sec
from cendekiara.core.clock import now
from cendekiara.core.context import Context
from cendekiara.core.errors import AppError
from cendekiara.core.models import Model
from cendekiara.core.registry import Command, command


class AttemptSaveIn(Model):
    attempt_id: str
    answers: dict[str, Any] | None = None
    timings: dict[str, Any] | None = None
    flags: list[str] | None = None


class AttemptSaveOut(Model):
    ok: bool = True
    updated_at: str


@command("attempt.save", summary="Save attempt progress")
class AttemptSave(Command[AttemptSaveIn, AttemptSaveOut]):
    def run(self, args: AttemptSaveIn, ctx: Context) -> AttemptSaveOut:
        uid = ctx.actor.require_uid()
        if False:  # admins may not save others' attempts
            pass
        doc = ctx.store.get("attempts", args.attempt_id)
        if not doc:
            raise AppError("not_found", "attempt not found")
        if doc.get("uid") != uid:
            # non-owner (including admin trying to save others) -> not_found
            raise AppError("not_found", "attempt not found")
        if doc.get("status") == "submitted":
            raise AppError("conflict", "attempt already submitted")
        # rate limit
        try:
            from cendekiara.core import config

            limit = int(getattr(config.settings, "attempt_save_rate_limit", 30))
            maxb = int(getattr(config.settings, "attempt_save_max_bytes", 20000))
        except Exception:
            limit, maxb = 30, 20000

        if not rate_limit.check_rate_limit(uid, "attempt_save", limit):
            raise AppError("rate_limited", "rate limited")
        payload = json.dumps(
            {"answers": args.answers, "timings": args.timings, "flags": args.flags}, ensure_ascii=False
        )
        if len(payload.encode("utf-8")) > maxb:
            raise AppError("invalid_args", "payload too large")

        # check deadline + grace
        deadline_at = doc.get("deadlineAt") or doc.get("deadline_at")
        if deadline_at:
            try:
                from datetime import datetime, timedelta

                dl = deadline_at
                dld = None
                if isinstance(dl, str):
                    try:
                        dld = datetime.fromisoformat(dl.replace("Z", "+00:00"))
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

        # merge
        answers = dict(doc.get("answers") or {})
        if args.answers:
            for k, v in args.answers.items():
                answers[k] = v
        timings = dict(doc.get("timings") or {})
        if args.timings:
            for k, v in args.timings.items():
                try:
                    timings[k] = float(v)
                except (TypeError, ValueError):
                    continue
            timings = cap_timings(timings)
        flags = list(doc.get("flags") or [])
        if args.flags is not None:
            flags = list(args.flags)
        updates = {
            "answers": answers,
            "timings": timings,
            "flags": flags,
            "updatedAt": now().isoformat(),
        }
        ctx.store.update("attempts", args.attempt_id, updates)
        return AttemptSaveOut(ok=True, updated_at=updates["updatedAt"])
