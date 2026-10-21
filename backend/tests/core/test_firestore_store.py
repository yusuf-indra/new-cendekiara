"""FirestoreStore: lazy init (no SDK at import), build_store wiring, injected client."""

from __future__ import annotations

import sys

import pytest

from cendekiara.core.firestore_store import FirestoreStore
from cendekiara.core.store import build_store
from tests.core.fake_firestore import FakeFirestoreClient


def test_constructing_the_store_imports_nothing(monkeypatch: pytest.MonkeyPatch) -> None:
    """Construction is lazy: no firebase_admin import, no network."""
    monkeypatch.setitem(sys.modules, "firebase_admin", None)
    monkeypatch.delitem(sys.modules, "firebase_admin.firestore", raising=False)
    store = FirestoreStore()
    assert store is not None


def test_using_the_store_needs_the_gcp_extra(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(sys.modules, "firebase_admin", None)
    monkeypatch.delitem(sys.modules, "firebase_admin.firestore", raising=False)
    with pytest.raises(RuntimeError, match="gcp"):
        FirestoreStore().get("users", "u1")


def test_an_injected_client_is_used_instead_of_the_default() -> None:
    client = FakeFirestoreClient()
    store = FirestoreStore(client)
    store.set("users", "u1", {"uid": "u1"})
    assert client.data["users"]["u1"] == {"uid": "u1"}


def test_build_store_memory_seeds_the_users() -> None:
    store = build_store("memory")
    assert store.get("users", "u-siti") is not None
    assert store.get("users", "u-admin") is not None


def test_build_store_firestore_constructs_offline() -> None:
    store = build_store("firestore")
    assert isinstance(store, FirestoreStore)
