"""Document store. Commands use only this interface; Firestore and memory implement it.

Paths are `collection/doc_id` (see docs/02-data-model.md). The memory store is used
for local dev (`STORE=memory`) and every test.
"""

from __future__ import annotations

import copy
import importlib
from typing import Any, Protocol, cast

from cendekiara.core.errors import AppError
from cendekiara.core.models import Model

Doc = dict[str, Any]


class Store(Protocol):
    def get(self, collection: str, doc_id: str) -> Doc | None: ...
    def set(self, collection: str, doc_id: str, doc: Doc) -> None: ...
    def update(self, collection: str, doc_id: str, fields: Doc) -> None: ...
    def delete(self, collection: str, doc_id: str) -> None: ...
    def list(self, collection: str, where: Doc | None = None, limit: int = 100) -> list[Doc]: ...


def load[M: Model](store: Store, collection: str, doc_id: str, model: type[M]) -> M:
    """Read one document as a model; missing -> AppError('not_found')."""
    doc = store.get(collection, doc_id)
    if doc is None:
        raise AppError("not_found", f"{collection}/{doc_id} not found")
    return model.from_doc(doc)


def save(store: Store, collection: str, doc_id: str, obj: Model) -> None:
    store.set(collection, doc_id, obj.to_doc())


class MemoryStore:
    """In-process store for dev and tests. Equality filters only, like simple Firestore queries."""

    def __init__(self, seed: dict[str, dict[str, Doc]] | None = None) -> None:
        self._data: dict[str, dict[str, Doc]] = copy.deepcopy(seed or {})

    def get(self, collection: str, doc_id: str) -> Doc | None:
        doc = self._data.get(collection, {}).get(doc_id)
        return copy.deepcopy(doc) if doc is not None else None

    def set(self, collection: str, doc_id: str, doc: Doc) -> None:
        self._data.setdefault(collection, {})[doc_id] = copy.deepcopy(doc)

    def update(self, collection: str, doc_id: str, fields: Doc) -> None:
        docs = self._data.setdefault(collection, {})
        if doc_id not in docs:
            raise AppError("not_found", f"{collection}/{doc_id} not found")
        docs[doc_id].update(copy.deepcopy(fields))

    def delete(self, collection: str, doc_id: str) -> None:
        self._data.get(collection, {}).pop(doc_id, None)

    def list(self, collection: str, where: Doc | None = None, limit: int = 100) -> list[Doc]:
        rows = [
            copy.deepcopy(d)
            for d in self._data.get(collection, {}).values()
            if all(d.get(k) == v for k, v in (where or {}).items())
        ]
        return rows[:limit]


def build_store(name: str) -> Store:
    """Build the store named in the settings: memory locally, Firestore in production."""
    if name == "memory":
        return MemoryStore()
    if name == "firestore":
        try:
            module = importlib.import_module("cendekiara.core.firestore_store")
        except ModuleNotFoundError as exc:
            raise AppError(
                "invalid_args",
                "STORE=firestore is not available yet (Phase 2): core/firestore_store.py is missing",
            ) from exc
        return cast(Store, module.FirestoreStore())
    raise AppError("invalid_args", f"Unknown store {name!r}")
