"""One store contract, run against MemoryStore and FirestoreStore (with a fake client)."""

from __future__ import annotations

import pytest

from cendekiara.core.firestore_store import FirestoreStore
from cendekiara.core.store import MemoryStore, Store
from tests.core.fake_firestore import FakeFirestoreClient


@pytest.fixture(params=["memory", "firestore"])
def store(request: pytest.FixtureRequest) -> Store:
    if request.param == "memory":
        return MemoryStore()
    return FirestoreStore(FakeFirestoreClient())


def test_get_returns_none_for_a_missing_document(store: Store) -> None:
    assert store.get("users", "nope") is None


def test_set_then_get_roundtrips(store: Store) -> None:
    store.set("users", "u1", {"uid": "u1", "lang": "id"})
    assert store.get("users", "u1") == {"uid": "u1", "lang": "id"}


def test_set_replaces_the_document(store: Store) -> None:
    store.set("users", "u1", {"uid": "u1", "lang": "id"})
    store.set("users", "u1", {"uid": "u1", "lang": "en"})
    assert store.get("users", "u1") == {"uid": "u1", "lang": "en"}


def test_update_merges_fields(store: Store) -> None:
    store.set("users", "u1", {"uid": "u1", "lang": "id"})
    store.update("users", "u1", {"lang": "en"})
    assert store.get("users", "u1") == {"uid": "u1", "lang": "en"}


def test_delete_removes_the_document(store: Store) -> None:
    store.set("users", "u1", {"uid": "u1"})
    store.delete("users", "u1")
    assert store.get("users", "u1") is None


def test_list_returns_every_document(store: Store) -> None:
    store.set("users", "u1", {"uid": "u1"})
    store.set("users", "u2", {"uid": "u2"})
    assert {doc["uid"] for doc in store.list("users")} == {"u1", "u2"}


def test_list_filters_with_where(store: Store) -> None:
    store.set("items", "i1", {"exam": "ielts", "section": "reading"})
    store.set("items", "i2", {"exam": "tpa-bappenas", "section": "verbal"})
    store.set("items", "i3", {"exam": "ielts", "section": "listening"})
    rows = store.list("items", {"exam": "ielts"})
    assert {row["section"] for row in rows} == {"reading", "listening"}


def test_list_respects_limit(store: Store) -> None:
    for index in range(5):
        store.set("items", f"i{index}", {"n": index})
    assert len(store.list("items", limit=2)) == 2
