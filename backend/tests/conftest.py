"""Shared fixtures: a seeded memory store and contexts for a student, an admin, a guest."""

from __future__ import annotations

import os
from collections.abc import Iterator
from datetime import UTC, datetime

import pytest

from cendekiara.core import clock, registry
from cendekiara.core.context import Actor, Context
from cendekiara.core.store import MemoryStore

# Tests always run the dev profile, whatever the shell has.
os.environ["APP_ENV"] = "dev"
os.environ["SITE"] = "id"
os.environ["STORE"] = "memory"
os.environ["AUTH_MODE"] = "dev"
os.environ["JOBS"] = "inline"

FROZEN_NOW = datetime(2026, 10, 21, 12, 0, tzinfo=UTC)

SEED = {
    "users": {
        "u-siti": {"uid": "u-siti", "email": "siti@example.com", "lang": "id"},
        "u-admin": {"uid": "u-admin", "email": "admin@example.com", "lang": "en"},
    },
}

registry.load_all()


@pytest.fixture(autouse=True)
def frozen_clock() -> Iterator[None]:
    """Freeze the clock so no test depends on the wall clock."""
    clock.freeze(FROZEN_NOW)
    yield
    clock.unfreeze()


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
