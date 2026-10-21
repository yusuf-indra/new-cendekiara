"""choice: multiple choice, True/False/Not Given, Yes/No/Not Given — one option id."""

from __future__ import annotations

from pydantic import Field

from cendekiara.core.models import Model
from cendekiara.core.plugins import Marks, Option, qtype


class ChoiceQuestion(Model):
    """One multiple-choice question."""

    id: str
    prompt: str
    options: list[Option] = Field(default_factory=list)


@qtype("choice", ChoiceQuestion)
def grade(question: ChoiceQuestion, key: list[str], answer: str) -> Marks:
    """1 mark when the single chosen option id is in the key."""
    correct = answer in key
    return Marks(correct=correct, marks=1.0 if correct else 0.0)
