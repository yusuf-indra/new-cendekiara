"""catalog.exam: one exam's public definition, and never an answer key."""

from __future__ import annotations

import pytest

from cendekiara.core import registry
from cendekiara.core.context import Context
from cendekiara.core.errors import AppError


def test_catalog_exam_returns_the_definition(guest_ctx: Context) -> None:
    data = registry.execute("catalog.exam", {"exam_id": "tpa-bappenas"}, guest_ctx).model_dump()
    assert data["id"] == "tpa-bappenas"
    assert data["scoring"] == "scale_200_800"
    assert data["status"] == "active"
    assert [section["id"] for section in data["sections"]] == ["verbal", "kuantitatif", "penalaran"]


def test_catalog_exam_unknown_is_not_found(guest_ctx: Context) -> None:
    with pytest.raises(AppError) as err:
        registry.execute("catalog.exam", {"exam_id": "nope"}, guest_ctx)
    assert err.value.code == "not_found"


def test_catalog_exam_is_public_readonly_and_cached() -> None:
    info = registry.get("catalog.exam")
    assert info.public is True
    assert info.readonly is True
    assert info.cache_seconds > 0


def test_catalog_exam_never_exposes_answer_keys(guest_ctx: Context) -> None:
    info = registry.get("catalog.exam")
    props = set(info.cls.output_model.model_json_schema(by_alias=True).get("properties", {}))
    assert props.isdisjoint({"answers", "keys", "explanations", "transcript", "aiCheck", "ai_check"})

    data = registry.execute("catalog.exam", {"exam_id": "ielts"}, guest_ctx).model_dump()
    for key in ("answers", "keys", "explanations", "transcript", "ai_check"):
        assert key not in data
