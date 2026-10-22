"""study.check: grade one answer of a study item.

This is the one place where a key may reach the browser: the item must be a
study item that is in no exam package, and the answer is graded on the server
(docs/10-security.md, rule 1).
"""

from __future__ import annotations

import json

from cendekiara.core import config, plugins, rate_limit
from cendekiara.core.context import Context
from cendekiara.core.errors import AppError
from cendekiara.core.items import Item, ItemKey, exam_package_item_ids
from cendekiara.core.models import Model
from cendekiara.core.plugins import Marks
from cendekiara.core.registry import Command, command


class StudyCheckIn(Model):
    item_id: str
    question_id: str
    answer: str | list[str]


class StudyCheckOut(Model):
    item_id: str
    question_id: str
    correct: bool
    marks: float
    explanation: str | None = None
    expected: list[str] | None = None


@command("study.check", summary="Grade one answer of a study item (server-side)")
class StudyCheck(Command[StudyCheckIn, StudyCheckOut]):
    def run(self, args: StudyCheckIn, ctx: Context) -> StudyCheckOut:
        uid = ctx.actor.require_uid()
        settings = ctx.settings or config.settings
        _check_limits(args, uid, settings)
        item = _study_item(ctx, args.item_id)
        key = _key(ctx, args.item_id)
        expected = key.answers.get(args.question_id)
        if expected is None:
            raise AppError("not_found", "question not found")
        group_type = _group_type(item, args.question_id)
        if group_type is None:
            raise AppError("not_found", "question not found")
        marks = _grade(group_type, expected, args.answer)
        return StudyCheckOut(
            item_id=args.item_id,
            question_id=args.question_id,
            correct=bool(marks.correct),
            marks=float(marks.marks),
            explanation=key.explanations.get(args.question_id),
            expected=expected,
        )


def _check_limits(args: StudyCheckIn, uid: str, settings: config.Settings) -> None:
    """The rate limit and the size limit of a check."""
    payload = json.dumps(
        {"itemId": args.item_id, "questionId": args.question_id, "answer": args.answer}, ensure_ascii=False
    )
    if len(payload.encode("utf-8")) > settings.study_check_max_bytes:
        raise AppError("invalid_args", "This answer is too large")
    if not rate_limit.limiter.allow(uid, "study.check", settings.study_check_rate_limit):
        raise AppError("rate_limited", "Too many checks, wait a moment")


def _study_item(ctx: Context, item_id: str) -> Item:
    """The item to check: active, a study item, and in no exam package."""
    if item_id in exam_package_item_ids(ctx.store):
        # An exam item: the check would reveal its key.
        raise AppError("not_found", "item not found")
    doc = ctx.store.get("items", item_id)
    if doc is None:
        raise AppError("not_found", "item not found")
    try:
        item = Item.from_doc(doc)
    except (ValueError, TypeError) as exc:
        raise AppError("not_found", "item not found") from exc
    if item.status != "active" or not item.usage.study:
        raise AppError("not_found", "item not found")
    return item


def _key(ctx: Context, item_id: str) -> ItemKey:
    """The key of the item (only for a study item that is in no exam package)."""
    doc = ctx.store.get("item_keys", item_id)
    if doc is None:
        raise AppError("not_found", "item not found")
    try:
        return ItemKey.from_doc(doc)
    except (ValueError, TypeError) as exc:
        raise AppError("not_found", "item not found") from exc


def _group_type(item: Item, question_id: str) -> str | None:
    """The question type of the question, from the group it belongs to."""
    for group in item.groups:
        for question in group.questions:
            if question.id == question_id:
                return group.type
    return None


def _grade(group_type: str, expected: list[str], answer: str | list[str]) -> Marks:
    """Grade the answer with the question-type plugin."""
    try:
        grade_fn = plugins.get_qtype(group_type)
        model = plugins.get_qtype_model(group_type)
    except AppError:
        return Marks(correct=False, marks=0.0)
    try:
        question = model.model_validate({"id": "", "prompt": ""})
    except (ValueError, TypeError):
        question = None
    try:
        return grade_fn(question, expected, answer)
    except (TypeError, ValueError):
        return Marks(correct=False, marks=0.0)
