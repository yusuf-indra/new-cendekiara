"""Who is calling: Firebase ID tokens, dev tokens and admin API tokens.

The uid always comes from a verified credential, never from request args
(docs/10-security.md rule 3). Tokens are never logged. API tokens are stored
as a SHA-256 hash only, so a leaked database does not leak credentials.
"""

from __future__ import annotations

import hashlib
import importlib
import logging
import secrets
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol, cast

from cendekiara.core import clock
from cendekiara.core.config import Settings
from cendekiara.core.context import Actor, Via
from cendekiara.core.errors import AppError
from cendekiara.core.store import Store

log = logging.getLogger(__name__)

TOKEN_PREFIX = "ck_"  # noqa: S105 - a prefix, not a secret
TOKEN_ENTROPY_BYTES = 32
LAST_USED_THROTTLE_SEC = 300

# The firebase-admin errors that mean "this ID token is not valid".
FIREBASE_ERROR_NAMES = (
    "InvalidIdTokenError",
    "ExpiredIdTokenError",
    "RevokedIdTokenError",
    "CertificateFetchError",
)


def generate_token() -> str:
    """A fresh API token: 'ck_' + 32 url-safe bytes."""
    return TOKEN_PREFIX + secrets.token_urlsafe(TOKEN_ENTROPY_BYTES)


def hash_token(token: str) -> str:
    """SHA-256 of the token; the only thing we store."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class Identity:
    """Who is calling, and how they got in."""

    actor: Actor
    via: Via = "web"


class TokenVerifier(Protocol):
    """Turns a bearer token into an Actor; raises AppError('invalid_token')."""

    def verify(self, token: str) -> Actor: ...


TokenDecoder = Callable[[str], Mapping[str, Any]]


class DevTokenVerifier:
    """AUTH_MODE=dev: 'dev:<uid>', 'dev:admin' and 'dev:<admin email>'."""

    def __init__(self, settings: Settings) -> None:
        if settings.app_env != "dev":
            raise AppError("invalid_args", "AUTH_MODE=dev is only allowed when APP_ENV=dev")
        self._settings = settings

    def verify(self, token: str) -> Actor:
        if not token.startswith("dev:"):
            raise AppError("invalid_token", "This is not a dev token")
        subject = token[len("dev:") :].strip()
        if not subject:
            raise AppError("invalid_token", "This dev token has no subject")
        if subject == "admin":
            return Actor(uid="admin", is_admin=True)
        if self._settings.is_admin_email(subject):
            return Actor(uid=subject, email=subject, is_admin=True)
        return Actor(uid=subject)


class FirebaseTokenVerifier:
    """Verifies a Firebase ID token (firebase-admin lives in the 'gcp' extra)."""

    def __init__(self, settings: Settings, decoder: TokenDecoder | None = None) -> None:
        self._settings = settings
        self._decoder = decoder or decode_firebase_token

    def verify(self, token: str) -> Actor:
        try:
            claims = self._decoder(token)
        except AppError:
            raise
        except Exception as exc:
            raise AppError("invalid_token", "The ID token could not be verified") from exc
        uid = claims.get("uid")
        if not isinstance(uid, str) or not uid:
            raise AppError("invalid_token", "The ID token has no uid")
        email = claims.get("email")
        mail = email if isinstance(email, str) else None
        return Actor(uid=uid, email=mail, is_admin=self._settings.is_admin_email(mail))


def decode_firebase_token(token: str) -> Mapping[str, Any]:
    """Verify an ID token with firebase-admin (imported lazily, so it stays optional).

    firebase-admin checks the signature and the expiry; its errors mean the
    token is not valid, never that the server is broken.
    """
    firebase_auth = _import_firebase_auth()
    _ensure_firebase_app()
    errors = _firebase_errors(firebase_auth)
    try:
        decoded = firebase_auth.verify_id_token(token)
    except errors as exc:
        # The class name only: the message of the SDK may hold the token.
        log.warning("firebase refused an ID token: %s", type(exc).__name__)
        raise AppError("invalid_token", "The ID token could not be verified") from exc
    return {"uid": decoded.get("uid"), "email": decoded.get("email")}


def _import_firebase_auth() -> Any:
    """The firebase_admin.auth module; firebase-admin stays an optional extra."""
    try:
        return importlib.import_module("firebase_admin.auth")
    except ImportError as exc:
        raise RuntimeError("AUTH_MODE=firebase needs firebase-admin: install the 'gcp' extra") from exc


def _ensure_firebase_app() -> None:
    """The default app holds the public keys; it is created once, on first use."""
    firebase_admin = cast(Any, importlib.import_module("firebase_admin"))
    try:
        firebase_admin.get_app()
    except ValueError:
        firebase_admin.initialize_app()


def _firebase_errors(module: Any) -> tuple[type[BaseException], ...]:
    """The firebase-admin errors that mean 'this token is not valid'.

    The classes are read from the imported module, so firebase-admin stays an
    optional dependency (the SDK may name them differently one day).
    """
    classes: list[type[BaseException]] = []
    for name in FIREBASE_ERROR_NAMES:
        candidate = getattr(module, name, None)
        if isinstance(candidate, type) and issubclass(candidate, BaseException):
            classes.append(candidate)
    classes.append(ValueError)
    return tuple(classes)


def default_verifier(settings: Settings) -> TokenVerifier:
    """The verifier of the configured auth mode."""
    if settings.auth_mode == "dev":
        return DevTokenVerifier(settings)
    return FirebaseTokenVerifier(settings)


def bearer_token(header: str | None) -> str | None:
    """The token of an 'Authorization: Bearer <token>' header.

    A missing or malformed header means "anonymous", not an error.
    """
    if not header:
        return None
    parts = header.split(None, 1)
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return None
    token = parts[1].strip()
    return token or None


class Authenticator:
    """Turns an Authorization header into an Identity."""

    def __init__(
        self,
        settings: Settings,
        store: Store,
        verifier: TokenVerifier | None = None,
    ) -> None:
        self._settings = settings
        self._store = store
        self._verifier = verifier or default_verifier(settings)

    def authenticate(self, header: str | None) -> Identity:
        """The caller of a request. An API token comes in as a remote admin."""
        token = bearer_token(header)
        if token is None:
            return Identity(Actor(uid=None))
        if token.startswith(TOKEN_PREFIX):
            return Identity(self._api_token_actor(token), "remote")
        return Identity(self._verifier.verify(token))

    def _api_token_actor(self, token: str) -> Actor:
        """The admin who created the token; unknown or revoked tokens are refused.

        The owner is re-checked on every use: a token loses its admin rights
        as soon as its owner is no longer an admin (docs/10-security.md rule 7).
        """
        token_id = hash_token(token)
        doc = self._store.get("api_tokens", token_id)
        if doc is None:
            raise AppError("invalid_token", "This API token is not valid")
        if doc.get("revokedAt"):
            raise AppError("invalid_token", "This API token was revoked")
        created_by = doc.get("createdBy")
        if not isinstance(created_by, str) or not created_by:
            raise AppError("invalid_token", "This API token is not valid")
        email = doc.get("createdByEmail")
        if not isinstance(email, str) or not self._settings.is_admin_email(email):
            raise AppError("invalid_token", "The owner of this API token is no longer an admin")
        self._touch(token_id, doc)
        return Actor(uid=created_by, email=email, is_admin=True)

    def _touch(self, token_id: str, doc: Mapping[str, Any]) -> None:
        """Remember when the token was last used (throttled, so requests stay cheap)."""
        now = clock.now()
        seen = _parse_iso(doc.get("lastUsedAt"))
        if seen is not None and (now - seen).total_seconds() < LAST_USED_THROTTLE_SEC:
            return
        self._store.update("api_tokens", token_id, {"lastUsedAt": now.isoformat()})


def _parse_iso(value: object) -> datetime | None:
    """Read an ISO-8601 timestamp; None when it is missing or unreadable."""
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None else None
