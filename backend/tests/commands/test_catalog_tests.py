"""catalog.tests: public, cached, active packages only, never item ids or keys."""

from __future__ import annotations

import pytest

from cendekiara.core import registry
from cendekiara.core.context import Context
from cendekiara.core.errors import AppError

KEY_FIELDS = {"answers", "keys", "explanations", "transcript", "ai_check", "aiCheck", "item_ids"}


def _test_doc(status: str = "active") -> dict:
    return {
        "id": "tpa-mini",
        "exam": "tpa-bappenas",
        "sections": {"kuantitatif": ["tpa-k-0101"], "verbal": ["tpa-v-0101"]},
        "durationSec": 180,
        "free": True,
        "wrongPenalty": 0,
        "status": status,
        "sites": ["id"],
    }


def test_catalog_tests_is_public_readonly_and_cached() -> None:
    info = registry.get("catalog.tests")
    assert info.public is True
    assert info.readonly is True
    assert info.cache_seconds > 0


def test_catalog_tests_lists_active_packages(guest_ctx: Context) -> None:
    guest_ctx.store.set("tests", "tpa-mini", _test_doc())
    out = registry.execute("catalog.tests", {"exam_id": "tpa-bappenas"}, guest_ctx)
    data = out.model_dump()
    assert [brief["id"] for brief in data["tests"]] == ["tpa-mini"]
    brief = data["tests"][0]
    assert brief["sections"] == [{"id": "kuantitatif", "count": 1}, {"id": "verbal", "count": 1}]


def test_catalog_tests_hides_drafts(guest_ctx: Context) -> None:
    guest_ctx.store.set("tests", "tpa-mini", _test_doc("draft"))
    out = registry.execute("catalog.tests", {"exam_id": "tpa-bappenas"}, guest_ctx)
    assert out.model_dump()["tests"] == []


def test_catalog_tests_never_exposes_item_ids_or_keys(guest_ctx: Context) -> None:
    guest_ctx.store.set("tests", "tpa-mini", _test_doc())
    out = registry.execute("catalog.tests", {"exam_id": "tpa-bappenas"}, guest_ctx)
    assert "tpa-k-0101" not in str(out.model_dump())
    assert "answers" not in str(out.model_dump())


def test_catalog_tests_schema_has_no_key_fields() -> None:
    info = registry.get("catalog.tests")
    schema = info.cls.output_model.model_json_schema(by_alias=True)

    def walk(node: dict) -> set[str]:
        props = node.get("properties", {})
        found = set(props)
        for child in props.values():
            if isinstance(child, dict):
                found |= walk(child)
        return found

    assert walk(schema).isdisjoint(KEY_FIELDS)


def test_catalog_tests_unknown_exam_is_not_found(guest_ctx: Context) -> None:
    with pytest.raises(AppError) as err:
        registry.execute("catalog.tests", {"exam_id": "nope"}, guest_ctx)
    assert err.value.code == "not_found"
