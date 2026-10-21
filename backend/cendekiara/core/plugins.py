"""Plugin discovery: exams, scoring methods and question types are plugins.

Each extension point is a folder or file the core discovers by import, so
adding one never edits core code (docs/04-exams.md). Exams are subpackages of
`cendekiara.exams` that define `EXAM = ExamDef(...)`; scoring methods and
question types are modules registered with the `@scoring` / `@qtype`
decorators.
"""

from __future__ import annotations

import importlib
import pkgutil
from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from cendekiara.core.errors import AppError
from cendekiara.core.models import Lang, Model

ExamStatus = Literal["active", "coming_soon"]


class ExamDef(BaseModel):
    """One exam plugin (docs/04-exams.md). Texts are i18n keys, never brand strings."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str
    category: str
    scoring: str  # scoring plugin id
    layout: str  # frontend layout plugin id
    content_lang: Lang  # language of the questions
    features: tuple[str, ...] = ()  # e.g. ("math",) = LaTeX on
    status: ExamStatus = "active"
    sections: dict[str, tuple[str, ...]] = Field(default_factory=dict)  # section -> topics
    sites: tuple[str, ...] = ("id",)


class SectionResult(Model):
    """Per-section totals of one attempt."""

    correct: int = 0
    wrong: int = 0
    blank: int = 0
    marks: float = 0.0


class RawResult(Model):
    """What a scoring plugin grades: per-section correct / wrong / blank / marks."""

    sections: dict[str, SectionResult] = Field(default_factory=dict)


class SectionSpec(Model):
    """The questions of one section, for scoring: how many it has."""

    total: int = 0


class TestSpec(Model):
    """Minimal package shape a scoring plugin reads (the full TestDef is Phase 4)."""

    __test__ = False  # not a pytest test class

    sections: dict[str, SectionSpec] = Field(default_factory=dict)


class Score(Model):
    """A scored attempt: the overall estimate plus per-section breakdown."""

    score: float
    score_type: str
    sections: dict[str, float] = Field(default_factory=dict)
    correct: int = 0
    wrong: int = 0
    blank: int = 0


class Marks(Model):
    """The grade of one question: earned marks and whether it was fully correct."""

    correct: bool = False
    marks: float = 0.0


class Option(Model):
    """One option of a multiple-choice question."""

    id: str
    text: str


ScoringFn = Callable[[RawResult, TestSpec], Score]
QTypeGrade = Callable[..., Marks]


@dataclass(frozen=True)
class QType:
    """A question type: its grading function and the model of one question."""

    grade: QTypeGrade
    model: type[Model]


_EXAMS: dict[str, ExamDef] = {}
_SCORING: dict[str, ScoringFn] = {}
_QTYPES: dict[str, QType] = {}
_LOADED_EXAMS: set[str] = set()


def register_exam(exam: ExamDef) -> ExamDef:
    """Register one exam definition; called by the discovery and by new plugins."""
    if exam.id in _EXAMS:
        raise RuntimeError(f"duplicate exam plugin: {exam.id}")
    _EXAMS[exam.id] = exam
    return exam


def scoring(name: str) -> Callable[[ScoringFn], ScoringFn]:
    """Register a scoring method under its id, e.g. ``@scoring("scale_200_800")``."""

    def wrap(fn: ScoringFn) -> ScoringFn:
        if name in _SCORING:
            raise RuntimeError(f"duplicate scoring plugin: {name}")
        _SCORING[name] = fn
        return fn

    return wrap


def qtype(name: str, model: type[Model]) -> Callable[[QTypeGrade], QTypeGrade]:
    """Register a question type under its id, e.g. ``@qtype("choice", ChoiceQuestion)``.

    `model` is the pydantic model of one question of this type, used by the
    single validation path (`core/items.py`) to check each question.
    """

    def wrap(fn: QTypeGrade) -> QTypeGrade:
        if name in _QTYPES:
            raise RuntimeError(f"duplicate qtype plugin: {name}")
        _QTYPES[name] = QType(grade=fn, model=model)
        return fn

    return wrap


def load_all() -> None:
    """Import every exam, scoring and question-type plugin so it registers."""
    _load_exams()
    _load_modules("cendekiara.scoring")
    _load_modules("cendekiara.qtypes")


def _load_exams() -> None:
    """Import each exam subpackage and read its ``EXAM`` definition."""
    import cendekiara.exams as pkg

    for mod in pkgutil.iter_modules(pkg.__path__):
        if not mod.ispkg:
            continue
        name = f"{pkg.__name__}.{mod.name}"
        if name in _LOADED_EXAMS:
            continue
        _LOADED_EXAMS.add(name)
        module = importlib.import_module(name)
        exam = getattr(module, "EXAM", None)
        if not isinstance(exam, ExamDef):
            raise RuntimeError(f"exam plugin {mod.name} must define EXAM = ExamDef(...)")
        register_exam(exam)


def _load_modules(package: str) -> None:
    """Import every module in a plugin package so its decorators run."""
    module = importlib.import_module(package)
    for mod in pkgutil.iter_modules(module.__path__):
        importlib.import_module(f"{package}.{mod.name}")


def get_exam(exam_id: str) -> ExamDef:
    """One exam definition, or AppError('not_found') for an unknown id."""
    try:
        return _EXAMS[exam_id]
    except KeyError:
        raise AppError("not_found", f"exam {exam_id!r} not found") from None


def all_exams() -> list[ExamDef]:
    """Every exam, sorted by id."""
    return sorted(_EXAMS.values(), key=lambda exam: exam.id)


def get_scoring(name: str) -> ScoringFn:
    """One scoring method, or AppError('not_found') for an unknown id."""
    try:
        return _SCORING[name]
    except KeyError:
        raise AppError("not_found", f"scoring plugin {name!r} not found") from None


def all_scoring() -> list[str]:
    """The ids of every scoring method, sorted."""
    return sorted(_SCORING)


def get_qtype(name: str) -> QTypeGrade:
    """One question-type grading function, or AppError('not_found') for an unknown id."""
    try:
        return _QTYPES[name].grade
    except KeyError:
        raise AppError("not_found", f"qtype plugin {name!r} not found") from None


def get_qtype_model(name: str) -> type[Model]:
    """The question model of a question type, or AppError('not_found')."""
    try:
        return _QTYPES[name].model
    except KeyError:
        raise AppError("not_found", f"qtype plugin {name!r} not found") from None


def all_qtypes() -> list[str]:
    """The ids of every question type, sorted."""
    return sorted(_QTYPES)
