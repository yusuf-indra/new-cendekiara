"""item.validate: one validation path, admin-only, and never an answer key in its output."""

from __future__ import annotations

import pytest

from cendekiara.core import registry
from cendekiara.core.context import Context
from cendekiara.core.errors import AppError
from tests.item_helpers import make_item, make_key

KEY_FIELDS = {"answers", "keys", "explanations", "transcript", "ai_check", "aiCheck"}


def test_item_validate_accepts_a_valid_item(admin_ctx: Context) -> None:
    out = registry.execute("item.validate", {"item": make_item(), "key": make_key()}, admin_ctx)
    data = out.model_dump()
    assert data["valid"] is True
    assert data["errors"] == []


def test_item_validate_rejects_an_unknown_exam(admin_ctx: Context) -> None:
    out = registry.execute("item.validate", {"item": make_item(exam="nope"), "key": make_key()}, admin_ctx)
    assert out.model_dump()["valid"] is False
    assert any("exam" in error for error in out.errors)


def test_item_validate_rejects_an_unknown_topic(admin_ctx: Context) -> None:
    item = make_item()
    item["groups"][0]["topic"] = "not-a-topic"
    out = registry.execute("item.validate", {"item": item, "key": make_key()}, admin_ctx)
    assert out.model_dump()["valid"] is False
    assert any("topic" in error for error in out.errors)


def test_item_validate_rejects_an_answer_to_an_unknown_option(admin_ctx: Context) -> None:
    out = registry.execute("item.validate", {"item": make_item(), "key": make_key(answer="Z")}, admin_ctx)
    assert out.model_dump()["valid"] is False
    assert any("unknown option" in error for error in out.errors)


def test_item_validate_rejects_a_key_for_another_item(admin_ctx: Context) -> None:
    out = registry.execute(
        "item.validate",
        {"item": make_item(), "key": make_key(item_id="other")},
        admin_ctx,
    )
    assert out.model_dump()["valid"] is False


def test_item_validate_needs_admin(ctx: Context) -> None:
    with pytest.raises(AppError) as err:
        registry.execute("item.validate", {"item": make_item()}, ctx)
    assert err.value.code == "admin_only"


def test_item_validate_needs_login(guest_ctx: Context) -> None:
    with pytest.raises(AppError) as err:
        registry.execute("item.validate", {"item": make_item()}, guest_ctx)
    assert err.value.code == "login_required"


def test_item_validate_output_never_exposes_keys() -> None:
    info = registry.get("item.validate")
    props = set(info.cls.output_model.model_json_schema(by_alias=True).get("properties", {}))
    assert props.isdisjoint(KEY_FIELDS)
