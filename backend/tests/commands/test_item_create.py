"""item.create: save an item and its key, conflict on a duplicate, admin-only."""

from __future__ import annotations

import pytest

from cendekiara.core import registry
from cendekiara.core.context import Context
from cendekiara.core.errors import AppError
from tests.item_helpers import make_item, make_key

KEY_FIELDS = {"answers", "keys", "explanations", "transcript", "ai_check", "aiCheck"}


def test_item_create_saves_the_item_and_key(admin_ctx: Context) -> None:
    out = registry.execute("item.create", {"item": make_item(), "key": make_key()}, admin_ctx)
    assert out.model_dump() == {"id": "tpa-test-1", "status": "active"}
    item = admin_ctx.store.get("items", "tpa-test-1")
    assert item is not None
    assert item["createdAt"]  # type: ignore[index]
    key = admin_ctx.store.get("item_keys", "tpa-test-1")
    assert key is not None
    assert key["answers"] == {"q1": ["B"]}  # type: ignore[index]


def test_item_create_may_skip_the_key(admin_ctx: Context) -> None:
    registry.execute("item.create", {"item": make_item()}, admin_ctx)
    assert admin_ctx.store.get("items", "tpa-test-1") is not None
    assert admin_ctx.store.get("item_keys", "tpa-test-1") is None


def test_item_create_conflicts_on_a_duplicate(admin_ctx: Context) -> None:
    registry.execute("item.create", {"item": make_item()}, admin_ctx)
    with pytest.raises(AppError) as err:
        registry.execute("item.create", {"item": make_item()}, admin_ctx)
    assert err.value.code == "conflict"


def test_item_create_rejects_an_invalid_item(admin_ctx: Context) -> None:
    item = make_item()
    item["groups"][0]["topic"] = "not-a-topic"
    with pytest.raises(AppError) as err:
        registry.execute("item.create", {"item": item}, admin_ctx)
    assert err.value.code == "invalid_args"


def test_item_create_needs_admin(ctx: Context) -> None:
    with pytest.raises(AppError) as err:
        registry.execute("item.create", {"item": make_item()}, ctx)
    assert err.value.code == "admin_only"


def test_item_create_needs_login(guest_ctx: Context) -> None:
    with pytest.raises(AppError) as err:
        registry.execute("item.create", {"item": make_item()}, guest_ctx)
    assert err.value.code == "login_required"


def test_item_create_output_never_exposes_keys() -> None:
    info = registry.get("item.create")
    props = set(info.cls.output_model.model_json_schema(by_alias=True).get("properties", {}))
    assert props.isdisjoint(KEY_FIELDS)
