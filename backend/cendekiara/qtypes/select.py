"""select: matching via a dropdown — one option id."""

from __future__ import annotations

from pydantic import Field

from cendekiara.core.models import Model
from cendekiara.core.plugins import Marks, Option, qtype


class SelectQuestion(Model):
    """One matching question answered through a dropdown."""

    id: str
    prompt: str
    options: list[Option] = Field(default_factory=list)


@qtype("select", SelectQuestion)
def grade(question: SelectQuestion, key: list[str], answer: str) -> Marks:
    """1 mark when the single selected option id is in the key."""
    correct = answer in key
    return Marks(correct=correct, marks=1.0 if correct else 0.0)
