"""bank.assemble: admin preview of a package, numbered, never any answer key."""

from __future__ import annotations

import pytest

from cendekiara.core import registry
from cendekiara.core.context import Context
from cendekiara.core.errors import AppError
from tests.item_helpers import make_item

KEY_FIELDS = {"answers", "keys", "explanations", "transcript", "ai_check", "aiCheck"}


def test_bank_assemble_numbers_and_loads_content(admin_ctx: Context) -> None:
    admin_ctx.store.set("items", "tpa-test-1", make_item())
    admin_ctx.store.set("items", "tpa-test-2", make_item(item_id="tpa-test-2"))
    out = registry.execute(
        "bank.assemble",
        {"exam": "tpa-bappenas", "sections": {"kuantitatif": ["tpa-test-1", "tpa-test-2"]}},
        admin_ctx,
    )
    data = out.model_dump()
    assert data["exam"] == "tpa-bappenas"
    section = data["sections"][0]
    assert section["id"] == "kuantitatif"
    numbers = [
        q["number"] for item in section["items"] for group in item["groups"] for q in group["questions"]
    ]
    assert numbers == [1, 2]
    assert data["sections"][0]["items"][0]["groups"][0]["questions"][0]["prompt"] == "2, 5, 10, 17, ..."


def test_bank_assemble_output_never_exposes_keys(admin_ctx: Context) -> None:
    admin_ctx.store.set("items", "tpa-test-1", make_item())
    admin_ctx.store.set("item_keys", "tpa-test-1", {"answers": {"q1": ["B"]}})
    out = registry.execute(
        "bank.assemble",
        {"exam": "tpa-bappenas", "sections": {"kuantitatif": ["tpa-test-1"]}},
        admin_ctx,
    )
    text = str(out.model_dump())
    assert "answers" not in text
    assert "explanations" not in text
    assert "transcript" not in text


def test_bank_assemble_missing_item_is_not_found(admin_ctx: Context) -> None:
    with pytest.raises(AppError) as err:
        registry.execute(
            "bank.assemble",
            {"exam": "tpa-bappenas", "sections": {"kuantitatif": ["nope"]}},
            admin_ctx,
        )
    assert err.value.code == "not_found"


def test_bank_assemble_retired_item_is_rejected(admin_ctx: Context) -> None:
    item = make_item()
    item["status"] = "retired"
    admin_ctx.store.set("items", "tpa-test-1", item)
    with pytest.raises(AppError) as err:
        registry.execute(
            "bank.assemble",
            {"exam": "tpa-bappenas", "sections": {"kuantitatif": ["tpa-test-1"]}},
            admin_ctx,
        )
    assert err.value.code == "invalid_args"


def test_bank_assemble_is_admin_only(ctx: Context) -> None:
    with pytest.raises(AppError) as err:
        registry.execute("bank.assemble", {"exam": "tpa-bappenas", "sections": {}}, ctx)
    assert err.value.code == "admin_only"


def test_bank_assemble_schema_has_no_key_fields() -> None:
    info = registry.get("bank.assemble")
    props = set(info.cls.output_model.model_json_schema(by_alias=True).get("properties", {}))
    assert props.isdisjoint(KEY_FIELDS)
