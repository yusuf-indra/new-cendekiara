"""A tiny in-memory stand-in for the firebase-admin Firestore client.

Used by the store-contract tests so the FirestoreStore can be tested with no
SDK, emulator or network. It implements only the API surface the store uses.
"""

from __future__ import annotations

import copy
from typing import Any


class FakeSnapshot:
    def __init__(self, exists: bool, data: dict[str, Any] | None = None) -> None:
        self._exists = exists
        self._data: dict[str, Any] = copy.deepcopy(data or {})

    @property
    def exists(self) -> bool:
        return self._exists

    def to_dict(self) -> dict[str, Any]:
        return copy.deepcopy(self._data)


class FakeDocRef:
    def __init__(self, data: dict[str, dict[str, dict[str, Any]]], collection: str, doc_id: str) -> None:
        self._data = data
        self._collection = collection
        self._doc_id = doc_id

    def get(self) -> FakeSnapshot:
        doc = self._data.get(self._collection, {}).get(self._doc_id)
        return FakeSnapshot(doc is not None, doc)

    def set(self, doc: dict[str, Any]) -> None:
        self._data.setdefault(self._collection, {})[self._doc_id] = copy.deepcopy(doc)

    def update(self, fields: dict[str, Any]) -> None:
        docs = self._data.setdefault(self._collection, {})
        if self._doc_id not in docs:
            raise KeyError(self._doc_id)
        docs[self._doc_id].update(copy.deepcopy(fields))

    def delete(self) -> None:
        self._data.get(self._collection, {}).pop(self._doc_id, None)


class FakeQuery:
    def __init__(
        self,
        data: dict[str, dict[str, dict[str, Any]]],
        collection: str,
        where: list[tuple[str, str, Any]],
        limit: int | None,
    ) -> None:
        self._data = data
        self._collection = collection
        self._where = where
        self._limit = limit

    def where(self, field: str, op: str, value: Any) -> FakeQuery:
        return FakeQuery(self._data, self._collection, [*self._where, (field, op, value)], self._limit)

    def limit(self, count: int) -> FakeQuery:
        return FakeQuery(self._data, self._collection, self._where, count)

    def stream(self) -> list[FakeSnapshot]:
        rows = self._data.get(self._collection, {})
        matched = [
            FakeSnapshot(True, doc)
            for doc in rows.values()
            if all(doc.get(field) == value for field, _, value in self._where)
        ]
        if self._limit is not None:
            matched = matched[: self._limit]
        return matched


class FakeCollection:
    def __init__(self, data: dict[str, dict[str, dict[str, Any]]], name: str) -> None:
        self._data = data
        self._name = name

    def document(self, doc_id: str) -> FakeDocRef:
        return FakeDocRef(self._data, self._name, doc_id)

    def where(self, field: str, op: str, value: Any) -> FakeQuery:
        return FakeQuery(self._data, self._name, [(field, op, value)], None)

    def limit(self, count: int) -> FakeQuery:
        return FakeQuery(self._data, self._name, [], count)

    def stream(self) -> list[FakeSnapshot]:
        return FakeQuery(self._data, self._name, [], None).stream()


class FakeFirestoreClient:
    def __init__(self) -> None:
        self.data: dict[str, dict[str, dict[str, Any]]] = {}

    def collection(self, name: str) -> FakeCollection:
        return FakeCollection(self.data, name)
