"""item.update: full replace of an item (and optional key), not_found, admin-only."""

from __future__ import annotations

import pytest

from cendekiara.core import registry
from cendekiara.core.context import Context
from cendekiara.core.errors import AppError
from tests.item_helpers import make_item, make_key


def test_item_update_replaces_the_item(admin_ctx: Context) -> None:
    registry.execute("item.create", {"item": make_item()}, admin_ctx)
    changed = make_item()
    changed["difficulty"] = 5
    changed["groups"][0]["questions"][0]["prompt"] = "3, 6, 11, 18, ..."
    out = registry.execute("item.update", {"item": changed, "key": make_key()}, admin_ctx)
    assert out.model_dump() == {"id": "tpa-test-1", "status": "active"}
    saved = admin_ctx.store.get("items", "tpa-test-1")
    assert saved is not None
    assert saved["difficulty"] == 5  # type: ignore[index]
    assert admin_ctx.store.get("item_keys", "tpa-test-1") is not None


def test_item_update_of_a_missing_item_is_not_found(admin_ctx: Context) -> None:
    with pytest.raises(AppError) as err:
        registry.execute("item.update", {"item": make_item()}, admin_ctx)
    assert err.value.code == "not_found"


def test_item_update_rejects_an_invalid_item(admin_ctx: Context) -> None:
    registry.execute("item.create", {"item": make_item()}, admin_ctx)
    bad = make_item()
    bad["groups"][0]["topic"] = "not-a-topic"
    with pytest.raises(AppError) as err:
        registry.execute("item.update", {"item": bad}, admin_ctx)
    assert err.value.code == "invalid_args"


def test_item_update_needs_admin(ctx: Context) -> None:
    with pytest.raises(AppError) as err:
        registry.execute("item.update", {"item": make_item()}, ctx)
    assert err.value.code == "admin_only"
