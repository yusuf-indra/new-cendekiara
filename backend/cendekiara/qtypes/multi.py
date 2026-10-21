"""multi: choose TWO/THREE — a list of option ids, exact set match."""

from __future__ import annotations

from pydantic import Field

from cendekiara.core.models import Model
from cendekiara.core.plugins import Marks, Option, qtype


class MultiQuestion(Model):
    """One question answered by choosing two or three options."""

    id: str
    prompt: str
    options: list[Option] = Field(default_factory=list)


@qtype("multi", MultiQuestion)
def grade(question: MultiQuestion, key: list[str], answer: list[str]) -> Marks:
    """1 mark when the chosen ids match the key exactly (order ignored)."""
    correct = set(answer) == set(key)
    return Marks(correct=correct, marks=1.0 if correct else 0.0)
