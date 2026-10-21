"""token.revoke: by id or by label; a revoked token never works again."""

from __future__ import annotations

import pytest

from cendekiara.core import registry
from cendekiara.core.auth import Authenticator, generate_token, hash_token
from cendekiara.core.config import Settings
from cendekiara.core.context import Context
from cendekiara.core.errors import AppError
from cendekiara.core.store import MemoryStore

SETTINGS = Settings(_env_file=None, app_env="dev", auth_mode="dev")


def _token(store: MemoryStore, label: str = "laptop") -> tuple[str, str]:
    """A token in the store; returns the token and its id."""
    token = generate_token()
    token_id = hash_token(token)
    store.set(
        "api_tokens",
        token_id,
        {"id": token_id, "label": label, "createdBy": "u-admin", "createdAt": "2026-10-21T12:00:00+00:00"},
    )
    return token, token_id


def test_an_admin_revokes_a_token_by_id(admin_ctx: Context) -> None:
    token, token_id = _token(admin_ctx.store)
    out = registry.execute("token.revoke", {"id": token_id}, admin_ctx)
    data = out.model_dump()
    assert data["id"] == token_id
    assert data["label"] == "laptop"
    assert admin_ctx.store.get("api_tokens", token_id)["revokedAt"]  # type: ignore[index]
    with pytest.raises(AppError):
        Authenticator(SETTINGS, admin_ctx.store).authenticate(f"Bearer {token}")


def test_an_admin_revokes_a_token_by_label(admin_ctx: Context) -> None:
    _, token_id = _token(admin_ctx.store, label="phone")
    out = registry.execute("token.revoke", {"label": "phone"}, admin_ctx)
    assert out.model_dump()["id"] == token_id
    assert admin_ctx.store.get("api_tokens", token_id)["revokedAt"]  # type: ignore[index]


def test_the_newest_token_with_a_label_is_revoked(admin_ctx: Context) -> None:
    _, first = _token(admin_ctx.store, label="phone")
    admin_ctx.store.update(
        "api_tokens",
        first,
        {"createdAt": "2026-10-20T12:00:00+00:00"},
    )
    _, second = _token(admin_ctx.store, label="phone")
    admin_ctx.store.update("api_tokens", second, {"createdAt": "2026-10-21T13:00:00+00:00"})
    out = registry.execute("token.revoke", {"label": "phone"}, admin_ctx)
    assert out.model_dump()["id"] == second


def test_revoking_an_unknown_id_is_not_found(admin_ctx: Context) -> None:
    with pytest.raises(AppError) as err:
        registry.execute("token.revoke", {"id": "nope"}, admin_ctx)
    assert err.value.code == "not_found"


def test_revoking_an_unknown_label_is_not_found(admin_ctx: Context) -> None:
    with pytest.raises(AppError) as err:
        registry.execute("token.revoke", {"label": "nope"}, admin_ctx)
    assert err.value.code == "not_found"


def test_revoking_without_an_id_or_a_label_is_invalid_args(admin_ctx: Context) -> None:
    with pytest.raises(AppError) as err:
        registry.execute("token.revoke", {}, admin_ctx)
    assert err.value.code == "invalid_args"


def test_a_user_may_not_revoke_a_token(ctx: Context) -> None:
    with pytest.raises(AppError) as err:
        registry.execute("token.revoke", {"id": "nope"}, ctx)
    assert err.value.code == "admin_only"


def test_a_revoked_token_is_revoked_again(admin_ctx: Context) -> None:
    _, token_id = _token(admin_ctx.store)
    first = registry.execute("token.revoke", {"id": token_id}, admin_ctx).model_dump()
    second = registry.execute("token.revoke", {"id": token_id}, admin_ctx).model_dump()
    assert first["revoked_at"] == second["revoked_at"]
