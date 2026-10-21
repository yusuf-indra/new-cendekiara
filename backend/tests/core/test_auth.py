"""The auth layer: dev tokens, Firebase ID tokens and admin API tokens."""

from __future__ import annotations

import hashlib
import sys
import types
from typing import Any

import pytest

from cendekiara.core.auth import (
    Authenticator,
    DevTokenVerifier,
    FirebaseTokenVerifier,
    bearer_token,
    decode_firebase_token,
    generate_token,
    hash_token,
)
from cendekiara.core.config import Settings
from cendekiara.core.context import Actor
from cendekiara.core.errors import AppError
from cendekiara.core.store import MemoryStore

SETTINGS = Settings(_env_file=None, app_env="dev", auth_mode="dev", admin_emails=["boss@example.com"])


class FakeInvalidIdTokenError(Exception):
    """Stands in for firebase_admin.auth.InvalidIdTokenError."""


class FakeExpiredIdTokenError(FakeInvalidIdTokenError):
    """Stands in for firebase_admin.auth.ExpiredIdTokenError."""


def _fake_firebase(monkeypatch: pytest.MonkeyPatch, verify_id_token: Any) -> None:
    """A fake firebase_admin and firebase_admin.auth, so no SDK is needed."""
    app = types.ModuleType("firebase_admin")
    app.get_app = lambda: None  # type: ignore[attr-defined]
    app.initialize_app = lambda: None  # type: ignore[attr-defined]
    auth = types.ModuleType("firebase_admin.auth")
    auth.verify_id_token = verify_id_token  # type: ignore[attr-defined]
    auth.InvalidIdTokenError = FakeInvalidIdTokenError  # type: ignore[attr-defined]
    auth.ExpiredIdTokenError = FakeExpiredIdTokenError  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "firebase_admin", app)
    monkeypatch.setitem(sys.modules, "firebase_admin.auth", auth)


def test_a_dev_token_gives_the_uid() -> None:
    identity = Authenticator(SETTINGS, MemoryStore()).authenticate("Bearer dev:u-siti")
    assert identity.actor.uid == "u-siti"
    assert identity.actor.is_admin is False
    assert identity.via == "web"


def test_the_dev_admin_token_is_an_admin() -> None:
    identity = Authenticator(SETTINGS, MemoryStore()).authenticate("Bearer dev:admin")
    assert identity.actor.is_admin is True


def test_a_dev_token_of_an_admin_email_is_an_admin() -> None:
    identity = Authenticator(SETTINGS, MemoryStore()).authenticate("Bearer dev:boss@example.com")
    assert identity.actor.is_admin is True
    assert identity.actor.email == "boss@example.com"


def test_a_malformed_header_is_anonymous() -> None:
    authenticator = Authenticator(SETTINGS, MemoryStore())
    assert authenticator.authenticate("Basic abc").actor.uid is None
    assert authenticator.authenticate("Bearer").actor.uid is None
    assert authenticator.authenticate(None).actor.uid is None


def test_a_token_that_is_not_a_dev_token_is_refused() -> None:
    authenticator = Authenticator(SETTINGS, MemoryStore())
    with pytest.raises(AppError) as err:
        authenticator.authenticate("Bearer nonsense")
    assert err.value.code == "invalid_token"


def test_the_dev_verifier_refuses_a_prod_profile() -> None:
    prod = Settings(_env_file=None, app_env="prod", store="firestore", auth_mode="firebase")
    with pytest.raises(AppError) as err:
        DevTokenVerifier(prod)
    assert err.value.code == "invalid_args"


def test_bearer_token_reads_the_header() -> None:
    assert bearer_token("Bearer abc") == "abc"
    assert bearer_token("bearer abc") == "abc"
    assert bearer_token("Token abc") is None
    assert bearer_token("") is None
    assert bearer_token(None) is None


def test_an_api_token_acts_as_the_admin_who_created_it() -> None:
    store = MemoryStore()
    token = generate_token()
    token_id = hash_token(token)
    store.set(
        "api_tokens",
        token_id,
        {"id": token_id, "label": "laptop", "createdBy": "u-admin", "createdByEmail": "boss@example.com"},
    )
    identity = Authenticator(SETTINGS, store).authenticate(f"Bearer {token}")
    assert identity.actor.uid == "u-admin"
    assert identity.actor.email == "boss@example.com"
    assert identity.actor.is_admin is True
    assert identity.via == "remote"


def test_an_api_token_stops_working_when_its_owner_is_no_longer_an_admin() -> None:
    store = MemoryStore()
    token = generate_token()
    token_id = hash_token(token)
    store.set(
        "api_tokens",
        token_id,
        {"id": token_id, "label": "laptop", "createdBy": "u-admin", "createdByEmail": "boss@example.com"},
    )
    without_boss = Settings(_env_file=None, app_env="dev", auth_mode="dev", admin_emails=[])
    with pytest.raises(AppError) as err:
        Authenticator(without_boss, store).authenticate(f"Bearer {token}")
    assert err.value.code == "invalid_token"
    assert err.value.message == "The owner of this API token is no longer an admin"


def test_an_api_token_without_an_owner_email_is_refused() -> None:
    """Tokens of an older version have no owner email: they are refused."""
    store = MemoryStore()
    token = generate_token()
    token_id = hash_token(token)
    store.set("api_tokens", token_id, {"id": token_id, "label": "laptop", "createdBy": "u-admin"})
    with pytest.raises(AppError) as err:
        Authenticator(SETTINGS, store).authenticate(f"Bearer {token}")
    assert err.value.code == "invalid_token"
    assert err.value.message == "The owner of this API token is no longer an admin"


def test_an_api_token_is_remembered_as_used() -> None:
    store = MemoryStore()
    token = generate_token()
    token_id = hash_token(token)
    store.set(
        "api_tokens",
        token_id,
        {"id": token_id, "label": "laptop", "createdBy": "u-admin", "createdByEmail": "boss@example.com"},
    )
    Authenticator(SETTINGS, store).authenticate(f"Bearer {token}")
    assert store.get("api_tokens", token_id) is not None
    assert store.get("api_tokens", token_id)["lastUsedAt"]  # type: ignore[index]


def test_a_revoked_api_token_is_refused() -> None:
    store = MemoryStore()
    token = generate_token()
    token_id = hash_token(token)
    store.set(
        "api_tokens",
        token_id,
        {
            "id": token_id,
            "label": "laptop",
            "createdBy": "u-admin",
            "createdByEmail": "boss@example.com",
            "revokedAt": "2026-10-21T12:00:00+00:00",
        },
    )
    with pytest.raises(AppError) as err:
        Authenticator(SETTINGS, store).authenticate(f"Bearer {token}")
    assert err.value.code == "invalid_token"


def test_an_unknown_api_token_is_refused() -> None:
    with pytest.raises(AppError) as err:
        Authenticator(SETTINGS, MemoryStore()).authenticate(f"Bearer {generate_token()}")
    assert err.value.code == "invalid_token"


def test_a_token_is_stored_as_its_hash_only() -> None:
    store = MemoryStore()
    token = generate_token()
    token_id = hash_token(token)
    store.set(
        "api_tokens",
        token_id,
        {"id": token_id, "label": "laptop", "createdBy": "u-admin", "createdByEmail": "boss@example.com"},
    )
    assert token_id == hashlib.sha256(token.encode("utf-8")).hexdigest()
    assert token not in str(store.list("api_tokens"))


def test_the_firebase_verifier_reads_the_claims() -> None:
    verifier = FirebaseTokenVerifier(SETTINGS, decoder=lambda token: {"uid": "u-siti", "email": "a@b.c"})
    actor = verifier.verify("an-id-token")
    assert actor.uid == "u-siti"
    assert actor.email == "a@b.c"
    assert actor.is_admin is False


def test_the_firebase_verifier_marks_an_admin_email() -> None:
    verifier = FirebaseTokenVerifier(
        SETTINGS, decoder=lambda token: {"uid": "u-boss", "email": "boss@example.com"}
    )
    assert verifier.verify("an-id-token").is_admin is True


def test_the_firebase_verifier_refuses_a_broken_token() -> None:
    def boom(token: str) -> dict[str, str]:
        raise ValueError("expired")

    verifier = FirebaseTokenVerifier(SETTINGS, decoder=boom)
    with pytest.raises(AppError) as err:
        verifier.verify("an-id-token")
    assert err.value.code == "invalid_token"


def test_the_firebase_verifier_refuses_a_token_without_a_uid() -> None:
    verifier = FirebaseTokenVerifier(SETTINGS, decoder=lambda token: {"email": "a@b.c"})
    with pytest.raises(AppError) as err:
        verifier.verify("an-id-token")
    assert err.value.code == "invalid_token"


def test_the_actor_of_the_system_is_an_admin() -> None:
    assert Actor.system().is_admin is True


def test_the_firebase_verifier_calls_verify_id_token(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[str] = []

    def verify_id_token(token: str) -> dict[str, str]:
        seen.append(token)
        return {"uid": "u-siti", "email": "siti@example.com"}

    _fake_firebase(monkeypatch, verify_id_token)
    actor = FirebaseTokenVerifier(SETTINGS).verify("an-id-token")
    assert seen == ["an-id-token"]
    assert actor.uid == "u-siti"
    assert actor.email == "siti@example.com"
    assert actor.is_admin is False


def test_a_refused_firebase_token_is_an_invalid_token(monkeypatch: pytest.MonkeyPatch) -> None:
    def verify_id_token(token: str) -> dict[str, str]:
        raise FakeInvalidIdTokenError("the token is broken")

    _fake_firebase(monkeypatch, verify_id_token)
    with pytest.raises(AppError) as err:
        decode_firebase_token("a-secret-id-token")
    assert err.value.code == "invalid_token"
    assert "a-secret-id-token" not in err.value.message


def test_an_expired_firebase_token_is_an_invalid_token(monkeypatch: pytest.MonkeyPatch) -> None:
    def verify_id_token(token: str) -> dict[str, str]:
        raise FakeExpiredIdTokenError("expired")

    _fake_firebase(monkeypatch, verify_id_token)
    with pytest.raises(AppError) as err:
        decode_firebase_token("an-id-token")
    assert err.value.code == "invalid_token"


def test_a_broken_firebase_token_is_an_invalid_token(monkeypatch: pytest.MonkeyPatch) -> None:
    def verify_id_token(token: str) -> dict[str, str]:
        raise ValueError("illegal token")

    _fake_firebase(monkeypatch, verify_id_token)
    with pytest.raises(AppError) as err:
        decode_firebase_token("an-id-token")
    assert err.value.code == "invalid_token"


def test_firebase_needs_the_gcp_extra(monkeypatch: pytest.MonkeyPatch) -> None:
    """firebase-admin stays optional: without it the profile is broken, not the token."""
    monkeypatch.setitem(sys.modules, "firebase_admin", None)
    monkeypatch.delitem(sys.modules, "firebase_admin.auth", raising=False)
    with pytest.raises(RuntimeError, match="gcp"):
        decode_firebase_token("an-id-token")
