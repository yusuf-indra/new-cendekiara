"""Item, item key, family and package (test) models, plus the single validation path.

Every way of adding a question (form, JSON import, AI) ends in `validate_item`
(docs/05-question-bank.md). The item model is shared by every exam; the
question-type plugins own the per-question models. Answer keys live in a
separate collection (`item_keys/`) and never reach an item output.
"""

from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import Field, ValidationError

from cendekiara.core import plugins
from cendekiara.core.errors import AppError
from cendekiara.core.models import Model
from cendekiara.core.plugins import Option
from cendekiara.core.store import Store

ItemStatus = Literal["draft", "review", "active", "retired"]
TestStatus = Literal["draft", "active", "retired"]
StimulusKind = Literal["passage", "audio", "image"]


class Usage(Model):
    """Which modes may show an item."""

    exam: bool = True
    practice: bool = True
    study: bool = False


class Paragraph(Model):
    """One labelled paragraph of a reading passage."""

    label: str
    text: str


class PassageStimulus(Model):
    """A reading passage: a title and labelled paragraphs."""

    kind: Literal["passage"] = "passage"
    title: str
    paragraphs: list[Paragraph] = Field(min_length=1)


class AudioStimulus(Model):
    """A listening recording: an audio URL and an optional TTS fallback."""

    kind: Literal["audio"] = "audio"
    url: str
    tts_fallback: str | None = None


class ImageStimulus(Model):
    """An image (a graph, diagram or picture) the questions refer to."""

    kind: Literal["image"] = "image"
    url: str


Stimulus = Annotated[
    PassageStimulus | AudioStimulus | ImageStimulus,
    Field(discriminator="kind"),
]


class Question(Model):
    """A loose question shape; `validate_item` re-checks it against its qtype model."""

    id: str
    prompt: str
    options: list[Option] | None = None
    max_words: int | None = None


class ItemGroup(Model):
    """One group of questions of a single question type (e.g. one passage's questions)."""

    id: str
    type: str  # question-type plugin id
    topic: str | None = None
    instructions: str | None = None
    options: list[Option] | None = None  # group-level options, or per question
    questions: list[Question] = Field(min_length=1)


class Item(Model):
    """`items/{itemId}`: one question unit. Never the answer key."""

    id: str
    exam: str  # exam plugin id
    section: str  # from the exam's taxonomy
    family_id: str | None = None
    tags: list[str] = Field(default_factory=list)
    difficulty: int = Field(ge=1, le=5)
    target_time_sec: int = Field(default=60, ge=1)
    status: ItemStatus = "draft"
    usage: Usage = Field(default_factory=Usage)
    sites: list[str] = Field(default_factory=lambda: ["id"])
    stimulus: Stimulus | None = None
    groups: list[ItemGroup] = Field(min_length=1)
    created_at: str | None = None
    updated_at: str | None = None


class ItemKey(Model):
    """`item_keys/{itemId}`: answers, explanations, transcript, AI check. Server only."""

    id: str  # the item id this key belongs to
    answers: dict[str, list[str]]
    explanations: dict[str, str] = Field(default_factory=dict)
    transcript: str | None = None
    ai_check: dict[str, Any] | None = None


class Family(Model):
    """`families/{familyId}`: near-identical questions sharing one solution method."""

    id: str
    name: str
    method: str | None = None
    video_url: str | None = None


class Test(Model):
    """`tests/{testId}`: a package — sections listing item ids (numbers assigned on assembly)."""

    __test__ = False  # not a pytest test class

    id: str
    exam: str
    sections: dict[str, list[str]]  # section id -> item ids, in display order
    duration_sec: int | None = None
    free: bool = False
    wrong_penalty: float = 0.0
    status: TestStatus = "draft"
    sites: list[str] = Field(default_factory=lambda: ["id"])
    created_at: str | None = None
    updated_at: str | None = None


def exam_package_item_ids(store: Store) -> set[str]:
    """The ids of the items that belong to any package in `tests/`.

    Every package counts, whatever its status: an item that is in a draft
    package must not leak into practice or study either, or its key could be
    harvested by building a practice set and reading the explanation.
    """
    used: set[str] = set()
    for row in store.list("tests", limit=1000):
        try:
            test = Test.from_doc(row)
        except (ValueError, TypeError):
            continue
        for item_ids in test.sections.values():
            used.update(item_ids)
    return used


def validate_item(item: Item, key: ItemKey | None, store: Store) -> list[str]:
    """Validate an item (and, when given, its key). Empty list means valid.

    Structure is enforced by the pydantic models; this checks what they cannot:
    the exam/section/topic taxonomy, the per-question shape of each question
    type, option/answer consistency, LaTeX only where the exam allows it, and
    that an optional family exists. Error messages never echo answer values.
    """
    errors: list[str] = []

    try:
        exam = plugins.get_exam(item.exam)
    except AppError:
        return [f"exam {item.exam!r} not found"]
    if item.section not in exam.sections:
        errors.append(f"section {item.section!r} is not in exam {item.exam!r}")

    if item.family_id and store.get("families", item.family_id) is None:
        errors.append(f"family {item.family_id!r} not found")

    if "math" not in exam.features and _has_latex(item):
        errors.append(f"LaTeX is not enabled for exam {item.exam!r}")

    topics = exam.sections.get(item.section, ())
    question_ids: list[str] = []
    for group in item.groups:
        errors.extend(_validate_group(item, group, topics, question_ids))

    if key is not None:
        errors.extend(_validate_key(item, key, question_ids))
    return errors


def _validate_group(
    item: Item, group: ItemGroup, topics: tuple[str, ...], question_ids: list[str]
) -> list[str]:
    """The questions of one group: qtype exists, topic fits, options present, answers consistent."""
    errors: list[str] = []
    try:
        plugins.get_qtype_model(group.type)
    except AppError:
        return [f"unknown question type {group.type!r}"]

    if group.topic and topics and group.topic not in topics:
        errors.append(f"topic {group.topic!r} is not in section {item.section!r}")

    for question in group.questions:
        question_ids.append(question.id)
        if not _question_matches_type(group.type, question):
            errors.append(f"question {question.id!r} is not a valid {group.type!r} question")
        options = question.options if question.options is not None else group.options
        if group.type in ("choice", "select", "multi") and not options:
            errors.append(f"question {question.id!r} has no options")
    return errors


def _question_matches_type(qtype: str, question: Question) -> bool:
    """Does the question validate against its question-type model? (Never raises.)"""
    model = plugins.get_qtype_model(qtype)
    try:
        model.model_validate(question.to_doc())
    except ValidationError:
        return False
    return True


def _validate_key(item: Item, key: ItemKey, question_ids: list[str]) -> list[str]:
    """The key must answer exactly the questions of the item, with known option ids."""
    errors: list[str] = []
    if key.id != item.id:
        errors.append("the key id does not match the item id")
    answers = key.answers or {}
    for question_id in question_ids:
        if question_id not in answers:
            errors.append(f"question {question_id!r} has no answer")
    for question_id in answers:
        if question_id not in question_ids:
            errors.append(f"answers reference an unknown question {question_id!r}")
    for group in item.groups:
        for question in group.questions:
            answer = answers.get(question.id)
            if answer is None:
                continue
            options = question.options if question.options is not None else group.options
            if group.type in ("choice", "select", "multi"):
                for option_id in answer:
                    if options is None or not any(option.id == option_id for option in options):
                        errors.append(f"question {question.id!r} answers an unknown option")
            elif group.type == "text" and not all(isinstance(value, str) and value for value in answer):
                errors.append(f"question {question.id!r} has an empty answer")
    return errors


def _has_latex(item: Item) -> bool:
    """Does any user-facing text contain an inline ``$…$`` span?"""
    texts: list[str] = [question.prompt for group in item.groups for question in group.questions]
    texts += [group.instructions for group in item.groups if group.instructions]
    for group in item.groups:
        texts += [option.text for option in (group.options or [])]
        for question in group.questions:
            texts += [option.text for option in (question.options or [])]
    if isinstance(item.stimulus, PassageStimulus):
        texts.append(item.stimulus.title)
        texts += [paragraph.text for paragraph in item.stimulus.paragraphs]
    return any("$" in text for text in texts)
