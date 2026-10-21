"""text: completion / short answer — free text, normalised before matching."""

from __future__ import annotations

import re

from cendekiara.core.models import Model
from cendekiara.core.plugins import Marks, qtype

_QUOTES = "'\"`\u2018\u2019\u201c\u201d"
_TRAILING_PUNCT = ".,!?;:"


def normalize_text(value: str) -> str:
    """Fold case and spacing, drop quotes and trailing punctuation.

    Any other variant must be listed in the key (docs/04-exams.md).
    """
    text = re.sub(r"\s+", " ", value.casefold()).strip()
    text = text.strip(_QUOTES)
    return text.strip().rstrip(_TRAILING_PUNCT).strip()


class TextQuestion(Model):
    """One short-answer question."""

    id: str
    prompt: str
    max_words: int | None = None


@qtype("text", TextQuestion)
def grade(question: TextQuestion, key: list[str], answer: str) -> Marks:
    """1 mark when the normalised answer matches any accepted variant."""
    expected = {normalize_text(variant) for variant in key}
    correct = normalize_text(answer) in expected
    return Marks(correct=correct, marks=1.0 if correct else 0.0)
