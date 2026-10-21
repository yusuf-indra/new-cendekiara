"""Firestore document store (Admin SDK), behind the Store interface.

firebase-admin stays an optional extra: it is imported lazily, on first use,
so importing this module (or building the store) never touches the network or
the SDK. Commands read and write Firestore only through this class
(docs/02-data-model.md, docs/10-security.md rule 2).
"""

from __future__ import annotations

import importlib
from typing import Any, cast

Doc = dict[str, Any]


class FirestoreStore:
    """Firestore through the Admin SDK. Inject a client for tests, else lazy."""

    def __init__(self, client: Any | None = None) -> None:
        self._client = client  # a test double, or None -> the default client, lazily
        self._lazy: Any | None = None

    def _db(self) -> Any:
        """The Firestore client, created on first use (never at import)."""
        if self._client is not None:
            return self._client
        if self._lazy is None:
            self._lazy = _default_client()
        return self._lazy

    def get(self, collection: str, doc_id: str) -> Doc | None:
        snapshot = self._db().collection(collection).document(doc_id).get()
        if not snapshot.exists:
            return None
        return cast(Doc, snapshot.to_dict())

    def set(self, collection: str, doc_id: str, doc: Doc) -> None:
        self._db().collection(collection).document(doc_id).set(doc)

    def update(self, collection: str, doc_id: str, fields: Doc) -> None:
        self._db().collection(collection).document(doc_id).update(fields)

    def delete(self, collection: str, doc_id: str) -> None:
        self._db().collection(collection).document(doc_id).delete()

    def list(self, collection: str, where: Doc | None = None, limit: int = 100) -> list[Doc]:
        query: Any = self._db().collection(collection)
        for field, value in (where or {}).items():
            query = query.where(field, "==", value)
        return [snapshot.to_dict() for snapshot in query.limit(limit).stream()]


def _default_client() -> Any:
    """The Admin SDK Firestore client (lazy import; needs the 'gcp' extra)."""
    firestore = _import_firestore()
    _ensure_firebase_app()
    return firestore.client()


def _import_firestore() -> Any:
    """The firebase_admin.firestore module; firebase-admin stays optional."""
    try:
        return importlib.import_module("firebase_admin.firestore")
    except ImportError as exc:
        raise RuntimeError("STORE=firestore needs firebase-admin: install the 'gcp' extra") from exc


def _ensure_firebase_app() -> None:
    """The default app; it is created once, on first use."""
    firebase_admin = cast(Any, importlib.import_module("firebase_admin"))
    try:
        firebase_admin.get_app()
    except ValueError:
        firebase_admin.initialize_app()
