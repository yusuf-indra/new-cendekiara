"""core/assemble.py: the function Phase 4 attempt.start will call directly."""

from __future__ import annotations

from cendekiara.core import assemble
from cendekiara.core.items import Test
from cendekiara.core.store import MemoryStore
from tests.item_helpers import make_item


def test_assemble_test_numbers_across_sections() -> None:
    store = MemoryStore()
    store.set("items", "i1", make_item())
    store.set("items", "i2", make_item(item_id="i2"))
    spec = Test(id="t", exam="tpa-bappenas", sections={"kuantitatif": ["i1", "i2"]})
    out = assemble.assemble_test(store, spec)
    questions = [
        q
        for section in out.sections
        for item in section.items
        for group in item.groups
        for q in group.questions
    ]
    assert [q.number for q in questions] == [1, 2]
    assert out.sections[0].id == "kuantitatif"


def test_assemble_test_output_has_no_key_fields() -> None:
    store = MemoryStore()
    store.set("items", "i1", make_item())
    spec = Test(id="t", exam="tpa-bappenas", sections={"kuantitatif": ["i1"]})
    out = assemble.assemble_test(store, spec)
    text = str(out.model_dump())
    for field in ("answers", "explanations", "transcript", "ai_check"):
        assert field not in text
