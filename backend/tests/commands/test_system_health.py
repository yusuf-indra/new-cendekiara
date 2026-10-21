"""system.health: public, readonly, and quiet about the profile for guests."""

from __future__ import annotations

import pytest

from cendekiara import __version__
from cendekiara.core import registry
from cendekiara.core.context import Context
from cendekiara.core.errors import AppError


def test_health_is_public_and_readonly() -> None:
    info = registry.get("system.health")
    assert info.public is True
    assert info.readonly is True
    assert info.admin_only is False


def test_guest_sees_only_that_the_service_is_up(guest_ctx: Context) -> None:
    data = registry.execute("system.health", {}, guest_ctx).model_dump()
    assert data["ok"] is True
    assert data["version"] == __version__
    assert data["env"] is None
    assert data["site"] is None
    assert data["store"] is None
    assert isinstance(data["time"], str)


def test_signed_in_actor_sees_the_profile(ctx: Context) -> None:
    data = registry.execute("system.health", {}, ctx).model_dump()
    assert data["env"] == "dev"
    assert data["site"] == "id"
    assert data["store"] == "memory"


def test_health_writes_nothing(ctx: Context) -> None:
    before = ctx.store.list("users")
    registry.execute("system.health", {}, ctx)
    assert ctx.store.list("users") == before


def test_health_takes_no_arguments(guest_ctx: Context) -> None:
    with pytest.raises(AppError) as err:
        registry.execute("system.health", {"nope": 1}, guest_ctx)
    assert err.value.code == "invalid_args"
