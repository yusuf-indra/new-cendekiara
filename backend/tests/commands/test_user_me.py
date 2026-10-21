"""user.me: the profile of the caller, and nobody else's."""

from __future__ import annotations

import pytest

from cendekiara.core import registry
from cendekiara.core.context import Actor, Context
from cendekiara.core.errors import AppError
from cendekiara.core.store import MemoryStore


def test_a_user_reads_own_profile(ctx: Context) -> None:
    out = registry.execute("user.me", {}, ctx)
    data = out.model_dump()
    assert data["uid"] == "u-siti"
    assert data["email"] == "siti@example.com"
    assert data["lang"] == "id"
    assert data["is_admin"] is False


def test_an_admin_reads_own_profile(admin_ctx: Context) -> None:
    out = registry.execute("user.me", {}, admin_ctx)
    assert out.model_dump()["is_admin"] is True


def test_a_guest_may_not_read_a_profile(guest_ctx: Context) -> None:
    with pytest.raises(AppError) as err:
        registry.execute("user.me", {}, guest_ctx)
    assert err.value.code == "login_required"


def test_a_user_without_a_profile_gets_not_found(mem: MemoryStore) -> None:
    ctx = Context(Actor(uid="u-nobody"), mem)
    with pytest.raises(AppError) as err:
        registry.execute("user.me", {}, ctx)
    assert err.value.code == "not_found"


def test_a_document_of_someone_else_is_not_found(ctx: Context) -> None:
    ctx.store.set("users", "u-siti", {"uid": "u-other", "lang": "id"})
    with pytest.raises(AppError) as err:
        registry.execute("user.me", {}, ctx)
    assert err.value.code == "not_found"


def test_me_takes_no_arguments(ctx: Context) -> None:
    with pytest.raises(AppError) as err:
        registry.execute("user.me", {"uid": "u-admin"}, ctx)
    assert err.value.code == "invalid_args"
