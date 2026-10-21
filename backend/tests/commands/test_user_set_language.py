"""REFERENCE TEST — happy path, then the errors that matter (login, invalid input)."""

from __future__ import annotations

import pytest

from cendekiara.core import registry
from cendekiara.core.context import Context
from cendekiara.core.errors import AppError


def test_set_language_updates_own_profile(ctx: Context) -> None:
    out = registry.execute("user.set_language", {"lang": "en"}, ctx)
    assert out.model_dump() == {"lang": "en", "previous": "id"}
    assert ctx.store.get("users", "u-siti")["lang"] == "en"  # type: ignore[index]
    assert ctx.store.get("users", "u-admin")["lang"] == "en"  # type: ignore[index]  # untouched


def test_set_language_needs_login(guest_ctx: Context) -> None:
    with pytest.raises(AppError) as err:
        registry.execute("user.set_language", {"lang": "en"}, guest_ctx)
    assert err.value.code == "login_required"


def test_set_language_rejects_unknown_language(ctx: Context) -> None:
    with pytest.raises(AppError) as err:
        registry.execute("user.set_language", {"lang": "fr"}, ctx)
    assert err.value.code == "invalid_args"
