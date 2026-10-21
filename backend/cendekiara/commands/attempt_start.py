"""attempt.start: start an exam/practice attempt."""

from __future__ import annotations

import uuid
from typing import Any, Literal

from cendekiara.core import assemble
from cendekiara.core.clock import now, now_iso
from cendekiara.core.context import Context
from cendekiara.core.errors import AppError
from cendekiara.core.items import Test
from cendekiara.core.models import Model
from cendekiara.core.registry import Command, command


class AttemptStartIn(Model):
    test_id: str | None = None
    mode: Literal["exam", "practice"] = "exam"
    package: dict[str, Any] | None = None  # for practice
    duration_sec: int | None = None


class AttemptStartOut(Model):
    attempt_id: str
    exam: str | None = None
    mode: str
    status: str
    deadline_at: str | None = None
    duration_sec: int | None = None
    free: bool = False
    wrong_penalty: float = 0.0
    package: dict[str, Any]


@command("attempt.start", summary="Start an attempt from a test package or practice package")
class AttemptStart(Command[AttemptStartIn, AttemptStartOut]):
    def run(self, args: AttemptStartIn, ctx: Context) -> AttemptStartOut:
        uid = ctx.actor.require_uid()
        if args.mode == "exam":
            if not args.test_id:
                raise AppError("invalid_args", "test_id required for exam mode")
            test_doc = ctx.store.get("tests", args.test_id)
            if not test_doc:
                raise AppError("not_found", f"tests/{args.test_id} not found")
            test = Test.from_doc(test_doc)
            if test.status != "active":
                raise AppError("not_found", f"tests/{args.test_id} not found")
            assembled = assemble.assemble_test(ctx.store, test)
            package_snapshot = assembled.model_dump(by_alias=True)
            duration = test.duration_sec or args.duration_sec
            free = test.free
            wrong_penalty = float(test.wrong_penalty)
            exam_id = test.exam
        elif args.mode == "practice":
            if not args.package:
                raise AppError("invalid_args", "package required for practice mode")
            package_snapshot = args.package
            exam_id = package_snapshot.get("exam") or package_snapshot.get("examId") or "tpa-bappenas"
            duration = (
                args.duration_sec
                if args.duration_sec is not None
                else package_snapshot.get("durationSec") or package_snapshot.get("duration_sec")
            )
            free = bool(package_snapshot.get("free", True))
            wrong_penalty = float(
                package_snapshot.get("wrongPenalty") or package_snapshot.get("wrong_penalty") or 0.0
            )
        else:
            raise AppError("invalid_args", "invalid mode")

        attempt_id = str(uuid.uuid4())
        started = now()
        deadline_at: str | None = None
        if duration and int(duration) > 0:
            from datetime import timedelta

            deadline_at = (started + timedelta(seconds=int(duration))).isoformat()

        attempt_doc: dict[str, Any] = {
            "id": attempt_id,
            "uid": uid,
            "mode": args.mode,
            "testId": args.test_id,
            "exam": exam_id,
            "packageSnapshot": package_snapshot,
            "status": "in_progress",
            "answers": {},
            "timings": {},
            "flags": [],
            "deadlineAt": deadline_at,
            "startedAt": started.isoformat(),
            "updatedAt": now_iso(),
            "pausedAt": None,
            "submittedAt": None,
            "free": free,
            "wrongPenalty": wrong_penalty,
            "durationSec": duration,
            "result": None,
        }
        ctx.store.set("attempts", attempt_id, attempt_doc)
        ctx.log.info("attempt started: %s for %s", attempt_id, uid)
        return AttemptStartOut(
            attempt_id=attempt_id,
            exam=exam_id,
            mode=args.mode,
            status="in_progress",
            deadline_at=deadline_at,
            duration_sec=duration,
            free=free,
            wrong_penalty=wrong_penalty,
            package=package_snapshot,
        )
