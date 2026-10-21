"""Shared fixtures: a seeded memory store and contexts for a student, an admin, a guest."""

from __future__ import annotations

import pytest

from cendekiara.core import registry
from cendekiara.core.context import Actor, Context
from cendekiara.core.store import MemoryStore

SEED = {
    "users": {
        "u-siti": {"uid": "u-siti", "email": "siti@example.com", "lang": "id"},
        "u-admin": {"uid": "u-admin", "email": "admin@example.com", "lang": "en"},
    },
}

registry.load_all()


@pytest.fixture
def mem() -> MemoryStore:
    return MemoryStore(SEED)


@pytest.fixture
def ctx(mem: MemoryStore) -> Context:
    """A signed-in student."""
    return Context(Actor(uid="u-siti"), mem)


@pytest.fixture
def admin_ctx(mem: MemoryStore) -> Context:
    return Context(Actor(uid="u-admin", is_admin=True), mem)


@pytest.fixture
def guest_ctx(mem: MemoryStore) -> Context:
    return Context(Actor(uid=None), mem)
