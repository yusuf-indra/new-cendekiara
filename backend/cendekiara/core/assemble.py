"""Assemble a package (test) into numbered content, never the answer keys.

`assemble_test` is the core function the `bank.assemble` command (an admin
preview) and, in Phase 4, `attempt.start` call. It reads only `items/` — the
output has prompts and options, never answers, explanations, transcripts or
`aiCheck` (docs/10-security.md rule 1).
"""

from __future__ import annotations

from itertools import count

from cendekiara.core import plugins
from cendekiara.core.errors import AppError
from cendekiara.core.items import Item, Stimulus, Test
from cendekiara.core.models import Model
from cendekiara.core.plugins import Option
from cendekiara.core.store import Store


class AssembledQuestion(Model):
    """One question with its global number and content (no answer)."""

    number: int
    id: str
    prompt: str
    options: list[Option] | None = None
    max_words: int | None = None


class AssembledGroup(Model):
    """One group of numbered questions."""

    id: str
    type: str
    topic: str | None = None
    instructions: str | None = None
    questions: list[AssembledQuestion]


class AssembledItem(Model):
    """One item with its stimulus and numbered groups."""

    id: str
    stimulus: Stimulus | None = None
    groups: list[AssembledGroup]


class AssembledSection(Model):
    """One section of an assembled package."""

    id: str
    items: list[AssembledItem]


class AssembledTest(Model):
    """A package with question numbers assigned. Content only, no keys."""

    exam: str
    duration_sec: int | None = None
    free: bool = False
    wrong_penalty: float = 0.0
    sections: list[AssembledSection]


def assemble_test(store: Store, spec: Test) -> AssembledTest:
    """Load the items of a package and number its questions. Only active items."""
    exam = plugins.get_exam(spec.exam)  # unknown exam -> not_found
    numbers = count(1)
    sections: list[AssembledSection] = []
    for section_id, item_ids in spec.sections.items():
        if section_id not in exam.sections:
            raise AppError("invalid_args", f"section {section_id!r} is not in exam {spec.exam!r}")
        items: list[AssembledItem] = []
        for item_id in item_ids:
            item = _load_active_item(store, item_id)
            groups = [
                AssembledGroup(
                    id=group.id,
                    type=group.type,
                    topic=group.topic,
                    instructions=group.instructions,
                    questions=[
                        AssembledQuestion(
                            number=next(numbers),
                            id=question.id,
                            prompt=question.prompt,
                            options=question.options if question.options is not None else group.options,
                            max_words=question.max_words,
                        )
                        for question in group.questions
                    ],
                )
                for group in item.groups
            ]
            items.append(AssembledItem(id=item.id, stimulus=item.stimulus, groups=groups))
        sections.append(AssembledSection(id=section_id, items=items))
    return AssembledTest(
        exam=spec.exam,
        duration_sec=spec.duration_sec,
        free=spec.free,
        wrong_penalty=spec.wrong_penalty,
        sections=sections,
    )


def _load_active_item(store: Store, item_id: str) -> Item:
    """One item for assembly; a missing or non-active item is an error."""
    doc = store.get("items", item_id)
    if doc is None:
        raise AppError("not_found", f"items/{item_id} not found")
    item = Item.from_doc(doc)
    if item.status != "active":
        raise AppError("invalid_args", f"item {item_id!r} is not active")
    return item
