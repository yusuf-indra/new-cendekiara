"""The seed loader: one JSON file per collection, feeds the memory store."""

from __future__ import annotations

from cendekiara.core.store import build_store
from cendekiara.seed import load_seed


def test_load_seed_reads_one_json_per_collection() -> None:
    seed = load_seed()
    assert "users" in seed
    assert seed["users"]["u-siti"]["uid"] == "u-siti"
    assert seed["users"]["u-siti"]["email"] == "siti@example.com"
    assert seed["users"]["u-admin"]["email"] == "admin@example.com"


def test_the_seed_feeds_the_memory_store() -> None:
    store = build_store("memory")
    assert store.get("users", "u-siti")["uid"] == "u-siti"  # type: ignore[index]
    assert store.get("users", "u-admin")["lang"] == "en"  # type: ignore[index]
