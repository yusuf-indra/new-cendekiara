"""The exam engine: deadlines, timings and the grading of a submitted attempt.

Everything here is server-side. The server alone decides the time (client
timestamps are never trusted), the answers that are graded are the ones stored
by `attempt.save`, and the answer keys are read here only, at submit time
(docs/10-security.md, "Exam engine security").

The answers, the timings and the flags of an attempt are keyed by the
*number* of the question (the global number the assembly gives it), never by
the id of the question inside its item: that id repeats in every item of a
package ("q1" of every passage), so it cannot identify an answer.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from cendekiara.core import plugins
from cendekiara.core.clock import now
from cendekiara.core.errors import AppError
from cendekiara.core.items import ItemKey
from cendekiara.core.models import Attempt, AttemptResult, AttemptResultSection
from cendekiara.core.plugins import Marks, RawResult, SectionResult, SectionSpec, TestSpec
from cendekiara.core.store import Store

# The longest time a student may spend on one question (docs/04-exams.md).
MAX_QUESTION_SECONDS = 3 * 3600

# The question type that takes a list of answers; the others take one.
MULTI_QTYPE = "multi"


@dataclass(frozen=True)
class Question:
    """One question of the package the attempt was taken with."""

    number: str
    section_id: str
    item_id: str
    question_id: str
    group_type: str


def parse_iso(value: object) -> datetime | None:
    """Read an ISO-8601 timestamp; None when it is missing or unreadable."""
    if not isinstance(value, str) or not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def deadline_of(attempt: Attempt) -> datetime | None:
    """The deadline of an attempt, or None when it has no timer."""
    return parse_iso(attempt.deadline_at)


def is_past_deadline(attempt: Attempt, grace_sec: int) -> bool:
    """Is the attempt past its deadline + grace? The server decides the time."""
    deadline = deadline_of(attempt)
    if deadline is None:
        return False
    return now() > deadline + timedelta(seconds=grace_sec)


def cap_timings(timings: dict[str, Any]) -> dict[str, float]:
    """Cap every question time at 3 h and drop the values that are not numbers."""
    capped: dict[str, float] = {}
    for question_id, raw in timings.items():
        try:
            seconds = float(raw)
        except (TypeError, ValueError):
            continue
        if seconds < 0:
            seconds = 0.0
        capped[question_id] = min(seconds, float(MAX_QUESTION_SECONDS))
    return capped


def questions_of(attempt: Attempt) -> dict[str, Question]:
    """The questions of the package, keyed by their number.

    The numbers come from the package snapshot stored in the attempt, so they
    stay the same even when the items of the bank change later on.
    """
    snapshot = attempt.package_snapshot
    snapshot = snapshot if isinstance(snapshot, dict) else {}
    questions: dict[str, Question] = {}
    for section in snapshot.get("sections") or []:
        if not isinstance(section, dict):
            continue
        section_id = section.get("id")
        if not isinstance(section_id, str):
            continue
        for item in section.get("items") or []:
            if not isinstance(item, dict):
                continue
            item_id = str(item.get("id"))
            for group in item.get("groups") or []:
                if not isinstance(group, dict):
                    continue
                group_type = str(group.get("type"))
                for question in group.get("questions") or []:
                    if not isinstance(question, dict):
                        continue
                    number = question.get("number")
                    question_id = question.get("id")
                    if not isinstance(number, int) or not isinstance(question_id, str):
                        continue
                    questions[str(number)] = Question(
                        number=str(number),
                        section_id=section_id,
                        item_id=item_id,
                        question_id=question_id,
                        group_type=group_type,
                    )
    return questions


def section_totals(attempt: Attempt) -> dict[str, int]:
    """How many questions every section of the package has."""
    totals: dict[str, int] = {}
    for question in questions_of(attempt).values():
        totals[question.section_id] = totals.get(question.section_id, 0) + 1
    return totals


def own_attempt(store: Store, attempt_id: str, uid: str) -> Attempt:
    """The attempt of this student.

    The attempt of another student does not exist for them: an admin included
    (docs/10-security.md, "Exam engine security").
    """
    doc = store.get("attempts", attempt_id)
    if doc is None or doc.get("uid") != uid:
        raise AppError("not_found", "attempt not found")
    try:
        return Attempt.from_doc(doc)
    except (ValueError, TypeError) as exc:
        raise AppError("not_found", "attempt not found") from exc


def normalize_answer(group_type: str, value: object) -> str | list[str]:
    """The answer of a question in the shape its question type expects.

    A single-answer question takes one string (a list with one answer is
    accepted); a `multi` question takes a list of option ids. An empty answer
    is blank, never wrong.
    """
    if group_type == MULTI_QTYPE:
        if isinstance(value, str):
            return [value] if value else []
        if isinstance(value, list):
            options = [option for option in value if isinstance(option, str)]
            if len(options) != len(value):
                raise AppError("invalid_args", "This answer is not a list of options")
            return options
        raise AppError("invalid_args", "This answer is not a list of options")
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        if len(value) > 1:
            raise AppError("invalid_args", "This question takes one answer")
        if not value:
            return ""
        first = value[0]
        if not isinstance(first, str):
            raise AppError("invalid_args", "This answer is not a text")
        return first
    raise AppError("invalid_args", "This answer is not a text")


def grade_attempt(store: Store, attempt: Attempt) -> AttemptResult:
    """Grade the stored answers of an attempt with the scoring plugin of its exam.

    The `wrongPenalty` of the package is applied by the core: every wrong
    answer costs `wrongPenalty` marks, so the marks the scoring plugin reads
    already carry the penalty (docs/04-exams.md).
    """
    questions = questions_of(attempt)
    totals = section_totals(attempt)
    answers = attempt.answers
    counted = _count_answers(store, questions, answers)
    penalty = _penalty(attempt)
    marked = _apply_penalty(counted, penalty)
    score = _score(attempt, marked, totals)
    times = _section_times(attempt, questions)
    return AttemptResult(
        score=score.score,
        score_type=score.score_type,
        correct=score.correct,
        wrong=score.wrong,
        blank=score.blank,
        wrong_penalty=penalty,
        sections=_section_results(marked, score.sections, times),
    )


def _count_answers(
    store: Store,
    questions: dict[str, Question],
    answers: dict[str, Any],
) -> dict[str, SectionResult]:
    """Count correct, wrong and blank answers per section, using the item keys."""
    counts: dict[str, SectionResult] = {}
    for question in questions.values():
        counts.setdefault(question.section_id, SectionResult())
    for number, question in questions.items():
        section = counts[question.section_id]
        answer = answers.get(number)
        if _is_blank(answer):
            section.blank += 1
            continue
        expected = _expected(store, question.item_id, question.question_id)
        if expected is None:
            section.blank += 1
            continue
        marks = _grade(question.group_type, expected, answer)
        if marks.correct:
            section.correct += 1
        else:
            section.wrong += 1
        section.marks += marks.marks
    return counts


def _is_blank(answer: object) -> bool:
    """Is the answer empty? A blank question counts as blank, never as wrong."""
    if answer is None:
        return True
    if isinstance(answer, str):
        return not answer.strip()
    if isinstance(answer, list):
        return not answer
    return False


def _expected(store: Store, item_id: str, question_id: str) -> list[str] | None:
    """The accepted answers of a question, read from the key (submit time only)."""
    doc = store.get("item_keys", item_id)
    if doc is None:
        return None
    try:
        key = ItemKey.from_doc(doc)
    except (ValueError, TypeError):
        return None
    return key.answers.get(question_id)


def _grade(group_type: str, expected: list[str], answer: object) -> Marks:
    """Grade one answer with the question-type plugin of its group."""
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


def _penalty(attempt: Attempt) -> float:
    """The wrong-answer penalty of the package (0 when there is none)."""
    return max(0.0, float(attempt.wrong_penalty))


def _apply_penalty(counted: dict[str, SectionResult], penalty: float) -> dict[str, SectionResult]:
    """Apply the wrong penalty to every section: each wrong answer costs marks."""
    if penalty <= 0:
        return counted
    penalised: dict[str, SectionResult] = {}
    for section_id, section in counted.items():
        marks = max(0.0, section.marks - penalty * section.wrong)
        penalised[section_id] = SectionResult(
            correct=section.correct, wrong=section.wrong, blank=section.blank, marks=marks
        )
    return penalised


def _score(
    attempt: Attempt,
    marked: dict[str, SectionResult],
    totals: dict[str, int],
) -> plugins.Score:
    """The score of the attempt, from the scoring plugin of its exam."""
    exam_id = attempt.exam
    raw_result = RawResult(sections=marked)
    spec = TestSpec(sections={sid: SectionSpec(total=total) for sid, total in totals.items()})
    if isinstance(exam_id, str) and exam_id:
        try:
            exam = plugins.get_exam(exam_id)
            return plugins.get_scoring(exam.scoring)(raw_result, spec)
        except AppError:
            pass
    marks = sum(section.marks for section in marked.values())
    correct = sum(section.correct for section in marked.values())
    wrong = sum(section.wrong for section in marked.values())
    blank = sum(section.blank for section in marked.values())
    return plugins.Score(
        score=marks,
        score_type="number",
        sections={},
        correct=correct,
        wrong=wrong,
        blank=blank,
    )


def _section_results(
    marked: dict[str, SectionResult],
    scores: dict[str, float],
    times: dict[str, float],
) -> dict[str, AttemptResultSection]:
    """The per-section result: counts, marks, score and the time spent."""
    return {
        section_id: AttemptResultSection(
            correct=section.correct,
            wrong=section.wrong,
            blank=section.blank,
            marks=round(section.marks, 4),
            score=scores.get(section_id),
            time_sec=round(times.get(section_id, 0.0), 2),
        )
        for section_id, section in marked.items()
    }


def _section_times(attempt: Attempt, questions: dict[str, Question]) -> dict[str, float]:
    """The time spent per section, from the timings of the attempt."""
    timings = attempt.timings
    times: dict[str, float] = {}
    for number, question in questions.items():
        raw = timings.get(number)
        if raw is None:
            continue
        times[question.section_id] = times.get(question.section_id, 0.0) + float(raw)
    return times
