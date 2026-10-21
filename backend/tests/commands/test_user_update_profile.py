"""user.update_profile: only the caller's own document."""

from __future__ import annotations

import pytest

from cendekiara.core import registry
from cendekiara.core.context import Actor, Context
from cendekiara.core.errors import AppError
from cendekiara.core.store import MemoryStore


def test_a_user_updates_own_profile(ctx: Context) -> None:
    out = registry.execute("user.update_profile", {"displayName": "Siti"}, ctx)
    data = out.model_dump()
    assert data["display_name"] == "Siti"
    assert data["uid"] == "u-siti"
    assert ctx.store.get("users", "u-siti")["displayName"] == "Siti"  # type: ignore[index]


def test_a_field_that_is_not_given_stays_as_it_is(ctx: Context) -> None:
    registry.execute("user.update_profile", {"displayName": "Siti"}, ctx)
    registry.execute("user.update_profile", {"lang": "en"}, ctx)
    doc = ctx.store.get("users", "u-siti")
    assert doc is not None
    assert doc["displayName"] == "Siti"
    assert doc["lang"] == "en"


def test_the_profile_of_another_user_is_not_touched(ctx: Context) -> None:
    registry.execute("user.update_profile", {"displayName": "Siti"}, ctx)
    assert ctx.store.get("users", "u-admin") is not None
    assert "displayName" not in ctx.store.get("users", "u-admin")  # type: ignore[operator]


def test_a_guest_may_not_update_a_profile(guest_ctx: Context) -> None:
    with pytest.raises(AppError) as err:
        registry.execute("user.update_profile", {"displayName": "Siti"}, guest_ctx)
    assert err.value.code == "login_required"


def test_an_unknown_field_is_invalid_args(ctx: Context) -> None:
    with pytest.raises(AppError) as err:
        registry.execute("user.update_profile", {"nickname": "S", "admin": True}, ctx)
    assert err.value.code == "invalid_args"


def test_an_empty_display_name_is_invalid_args(ctx: Context) -> None:
    with pytest.raises(AppError) as err:
        registry.execute("user.update_profile", {"displayName": ""}, ctx)
    assert err.value.code == "invalid_args"


def test_a_document_of_someone_else_is_not_found(ctx: Context) -> None:
    ctx.store.set("users", "u-siti", {"uid": "u-other", "lang": "id"})
    with pytest.raises(AppError) as err:
        registry.execute("user.update_profile", {"displayName": "Siti"}, ctx)
    assert err.value.code == "not_found"


def test_a_user_without_a_profile_gets_one(mem: MemoryStore) -> None:
    ctx = Context(Actor(uid="u-new"), mem)
    out = registry.execute("user.update_profile", {"displayName": "New"}, ctx)
    assert out.model_dump()["display_name"] == "New"
    assert mem.get("users", "u-new") is not None
