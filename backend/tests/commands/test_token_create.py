"""token.create: an admin token, shown once and stored as a hash only."""

from __future__ import annotations

import hashlib
from dataclasses import replace

import pytest

from cendekiara.core import registry
from cendekiara.core.context import Actor, Context
from cendekiara.core.errors import AppError
from cendekiara.core.store import MemoryStore


def test_an_admin_creates_a_token(admin_ctx: Context) -> None:
    out = registry.execute("token.create", {"label": "laptop"}, admin_ctx)
    data = out.model_dump()
    assert data["token"].startswith("ck_")
    assert data["label"] == "laptop"
    assert data["id"] == hashlib.sha256(data["token"].encode("utf-8")).hexdigest()


def test_the_token_is_stored_as_its_hash_only(admin_ctx: Context) -> None:
    out = registry.execute("token.create", {"label": "laptop"}, admin_ctx)
    token = out.model_dump()["token"]
    rows = admin_ctx.store.list("api_tokens")
    assert len(rows) == 1
    doc = rows[0]
    assert doc["createdBy"] == "u-admin"
    assert doc["createdByEmail"] == "admin@example.com"
    assert doc["label"] == "laptop"
    assert token not in str(doc)
    expected_id = hashlib.sha256(token.encode("utf-8")).hexdigest()
    assert admin_ctx.store.get("api_tokens", expected_id) == doc


def test_the_token_document_has_only_the_hash_fields(admin_ctx: Context) -> None:
    registry.execute("token.create", {"label": "laptop"}, admin_ctx)
    doc = admin_ctx.store.list("api_tokens")[0]
    assert set(doc) == {"id", "label", "createdBy", "createdByEmail", "createdAt"}


def test_an_admin_without_an_email_may_not_create_a_token(mem: MemoryStore) -> None:
    """Without an owner email the token could never be re-checked."""
    ctx = Context(Actor(uid="u-admin", is_admin=True), mem)
    with pytest.raises(AppError) as err:
        registry.execute("token.create", {"label": "laptop"}, ctx)
    assert err.value.code == "invalid_args"
    assert mem.list("api_tokens") == []


def test_a_user_may_not_create_a_token(ctx: Context) -> None:
    with pytest.raises(AppError) as err:
        registry.execute("token.create", {"label": "laptop"}, ctx)
    assert err.value.code == "admin_only"


def test_a_guest_may_not_create_a_token(guest_ctx: Context) -> None:
    with pytest.raises(AppError) as err:
        registry.execute("token.create", {"label": "laptop"}, guest_ctx)
    assert err.value.code == "login_required"


def test_a_token_needs_a_label(admin_ctx: Context) -> None:
    with pytest.raises(AppError) as err:
        registry.execute("token.create", {"label": ""}, admin_ctx)
    assert err.value.code == "invalid_args"


def test_a_token_is_not_allowed_from_a_job(admin_ctx: Context) -> None:
    ctx = replace(admin_ctx, via="job")
    with pytest.raises(AppError) as err:
        registry.execute("token.create", {"label": "laptop"}, ctx)
    assert err.value.code == "invalid_args"


def test_a_token_is_not_allowed_from_the_remote_cli(admin_ctx: Context) -> None:
    ctx = replace(admin_ctx, via="remote")
    with pytest.raises(AppError) as err:
        registry.execute("token.create", {"label": "laptop"}, ctx)
    assert err.value.code == "invalid_args"
