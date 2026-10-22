"""study.check: check answer for a study item."""

from __future__ import annotations

import json
from typing import Any

from cendekiara.core import plugins, rate_limit
from cendekiara.core.context import Context
from cendekiara.core.errors import AppError
from cendekiara.core.items import Item, ItemKey, Test
from cendekiara.core.models import Model
from cendekiara.core.registry import Command, command


class StudyCheckIn(Model):
    item_id: str
    question_id: str
    answer: str | list[str]


class StudyCheckOut(Model):
    correct: bool
    marks: float
    explanation: str | None = None
    expected: list[str] | None = None


def _items_in_any_test(store: Any) -> set[str]:
    used = set()
    try:
        tests = store.list("tests", limit=10000)
        for t in tests:
            try:
                test = Test.from_doc(t)
                for _, item_ids in test.sections.items():
                    for iid in item_ids:
                        used.add(iid)
            except (ValueError, TypeError):
                continue
    except (ValueError, TypeError):
        pass
    return used


@command("study.check", summary="Check a study answer")
class StudyCheck(Command[StudyCheckIn, StudyCheckOut]):
    def run(self, args: StudyCheckIn, ctx: Context) -> StudyCheckOut:
        uid = ctx.actor.require_uid()
        try:
            from cendekiara.core import config

            limit = int(getattr(config.settings, "study_check_rate_limit", 60))
            maxb = int(getattr(config.settings, "study_check_max_bytes", 10000))
        except Exception:
            limit, maxb = 60, 10000

        if not rate_limit.check_rate_limit(uid, "study_check", limit):
            raise AppError("rate_limited", "rate limited")
        payload = json.dumps(
            {"item_id": args.item_id, "question_id": args.question_id, "answer": args.answer},
            ensure_ascii=False,
        )
        if len(payload.encode("utf-8")) > maxb:
            raise AppError("invalid_args", "payload too large")

        used = _items_in_any_test(ctx.store)
        if args.item_id in used:
            raise AppError("not_found", "item not found")
        item_doc = ctx.store.get("items", args.item_id)
        if not item_doc:
            raise AppError("not_found", "item not found")
        try:
            item = Item.from_doc(item_doc)
        except (ValueError, TypeError) as exc:
            raise AppError("not_found", "item not found") from exc
        if item.status != "active" or not item.usage.study:
            raise AppError("not_found", "item not found")
        key_doc = ctx.store.get("item_keys", args.item_id)
        if not key_doc:
            raise AppError("not_found", "item not found")
        try:
            key = ItemKey.from_doc(key_doc)
        except (ValueError, TypeError) as exc:
            raise AppError("not_found", "item not found") from exc
        expected = key.answers.get(args.question_id)
        if expected is None:
            raise AppError("not_found", "item not found")
        # find question type
        gtype = None
        for g in item.groups:
            for q in g.questions:
                if q.id == args.question_id:
                    gtype = g.type
                    break
            if gtype:
                break
        if not gtype:
            raise AppError("not_found", "item not found")
        try:
            grade_fn = plugins.get_qtype(gtype)
            qmodel = plugins.get_qtype_model(gtype)
            try:
                qinst = qmodel.model_validate({"id": args.question_id, "prompt": ""})
            except Exception:
                qinst = type("Q", (), {"id": args.question_id})()
            try:
                marks = grade_fn(qinst, expected, args.answer)
            except TypeError:
                try:
                    marks = grade_fn(qinst, args.answer, expected)
                except Exception:
                    from cendekiara.core.plugins import Marks

                    marks = Marks(correct=False, marks=0.0)
        except Exception:
            from cendekiara.core.plugins import Marks

            marks = Marks(correct=False, marks=0.0)
        explanation = key.explanations.get(args.question_id) if hasattr(key, "explanations") else None
        return StudyCheckOut(
            correct=bool(marks.correct), marks=float(marks.marks), explanation=explanation, expected=expected
        )
