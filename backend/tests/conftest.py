"""Shared fixtures: a seeded memory store and contexts for a student, an admin, a guest."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from cendekiara.api.app import create_app
from cendekiara.core import clock, jobs, plugins, registry
from cendekiara.core.config import Settings
from cendekiara.core.context import Actor, Context
from cendekiara.core.store import MemoryStore, Store

FROZEN_NOW = datetime(2026, 10, 21, 12, 0, tzinfo=UTC)

SEED = {
    "users": {
        "u-siti": {"uid": "u-siti", "email": "siti@example.com", "lang": "id"},
        "u-admin": {"uid": "u-admin", "email": "admin@example.com", "lang": "en"},
    },
}

registry.load_all()
plugins.load_all()


@pytest.fixture(autouse=True)
def frozen_clock() -> Iterator[None]:
    """Freeze the clock so no test depends on the wall clock."""
    clock.freeze(FROZEN_NOW)
    yield
    clock.unfreeze()


# The real dispatcher of the queue, kept so a test can ask for the real behaviour.
_real_dispatch = jobs._dispatch


def _skip_dispatch(job_id: str, store: Store, settings: Settings, site: str) -> None:
    """Queue the job but do not start it: the test runs the job itself."""


@pytest.fixture(autouse=True)
def no_background_dispatch(monkeypatch: pytest.MonkeyPatch) -> None:
    """A queued job never starts a background thread in a test.

    In inline mode the queue runs the job in a thread. A test that runs the
    job itself (`jobs.run_job`) would race with that thread: the thread takes
    the job out of the queue and the test then reads the job document while it
    still runs. The dispatch is replaced, so the job stays "queued" until the
    test runs it.
    """
    monkeypatch.setattr(jobs, "_dispatch", _skip_dispatch)


@pytest.fixture
def real_dispatch(monkeypatch: pytest.MonkeyPatch) -> None:
    """Restore the real dispatcher: the queue really dispatches the job."""
    monkeypatch.setattr(jobs, "_dispatch", _real_dispatch)


@pytest.fixture
def mem() -> MemoryStore:
    return MemoryStore(SEED)


@pytest.fixture
def ctx(mem: MemoryStore) -> Context:
    """A signed-in student."""
    return Context(Actor(uid="u-siti"), mem)


@pytest.fixture
def admin_ctx(mem: MemoryStore) -> Context:
    return Context(Actor(uid="u-admin", email="admin@example.com", is_admin=True), mem)


@pytest.fixture
def guest_ctx(mem: MemoryStore) -> Context:
    return Context(Actor(uid=None), mem)


@pytest.fixture
def jobs_settings() -> Settings:
    """The dev settings used by the job tests (inline jobs, one admin email)."""
    return Settings(
        _env_file=None,
        app_env="dev",
        site="id",
        store="memory",
        auth_mode="dev",
        jobs="inline",
        admin_emails=["admin@example.com"],
    )


@pytest.fixture
def api_settings() -> Settings:
    """The settings of the API tests: the dev profile, set explicitly."""
    return Settings(
        _env_file=None,
        app_env="dev",
        site="id",
        store="memory",
        auth_mode="dev",
        jobs="inline",
        admin_emails=["admin@example.com"],
        site_url="https://cendekiara.test",
        capacitor_origin="capacitor://localhost",
    )


@pytest.fixture
def api_client(mem: MemoryStore, api_settings: Settings) -> TestClient:
    """A client of the API, with the seeded memory store."""
    return TestClient(create_app(store=mem, settings=api_settings))
