"""item.import: dry run by default, saves valid items, reports invalid ones, never leaks keys."""

from __future__ import annotations

import pytest

from cendekiara.core import jobs, registry
from cendekiara.core.config import Settings
from cendekiara.core.context import Actor, Context
from cendekiara.core.errors import AppError
from cendekiara.core.store import MemoryStore
from tests.item_helpers import make_item, make_key

KEY_FIELDS = {"answers", "keys", "explanations", "transcript", "ai_check", "aiCheck"}


def _import(mem: MemoryStore, args: dict, settings: Settings) -> dict:
    """Run item.import through the queue and the worker, then return the job result.

    The `no_background_dispatch` fixture keeps the queue from starting the
    inline thread, so this test runs the job itself.
    """
    ctx = Context(Actor(uid="u-admin", email="admin@example.com", is_admin=True), mem, settings=settings)
    out = registry.execute("item.import", args, ctx)
    jobs.run_job(out.job_id, mem, settings, "id")
    doc = mem.get("jobs", out.job_id)
    assert doc is not None
    assert doc["status"] == "done"
    return doc["result"]


def test_item_import_is_queued_and_admin() -> None:
    info = registry.get("item.import")
    assert info.queued is True
    assert info.admin_only is True


def test_item_import_dry_run_is_the_default(mem: MemoryStore, jobs_settings: Settings) -> None:
    result = _import(mem, {"items": [make_item()], "keys": {"tpa-test-1": make_key()}}, jobs_settings)
    assert result["dryRun"] is True
    assert result["total"] == 1
    assert result["valid"] == 1
    assert result["saved"] == 0
    assert mem.get("items", "tpa-test-1") is None  # nothing saved


def test_item_import_saves_valid_and_reports_invalid(mem: MemoryStore, jobs_settings: Settings) -> None:
    good = make_item()
    bad = {"exam": "tpa-bappenas"}  # no id
    result = _import(
        mem,
        {"items": [good, bad], "keys": {"tpa-test-1": make_key()}, "dry_run": False},
        jobs_settings,
    )
    assert result["valid"] == 1
    assert result["invalid"] == 1
    assert result["saved"] == 1
    assert mem.get("items", "tpa-test-1") is not None
    assert mem.get("item_keys", "tpa-test-1") is not None


def test_item_import_reports_a_bad_key(mem: MemoryStore, jobs_settings: Settings) -> None:
    result = _import(
        mem,
        {"items": [make_item()], "keys": {"tpa-test-1": {"answers": "nope"}}, "dry_run": True},
        jobs_settings,
    )
    assert result["invalid"] == 1
    assert any("key" in error for report in result["reports"] for error in report["errors"])


def test_item_import_reports_never_expose_keys(mem: MemoryStore, jobs_settings: Settings) -> None:
    result = _import(
        mem,
        {"items": [make_item()], "keys": {"tpa-test-1": make_key()}, "dry_run": True},
        jobs_settings,
    )
    for report in result["reports"]:
        assert set(report) == {"id", "ok", "saved", "errors"}
        for error in report["errors"]:
            assert all(field not in error for field in ("answers", "B"))


def test_item_import_needs_admin(ctx: Context) -> None:
    with pytest.raises(AppError) as err:
        registry.execute("item.import", {"items": [make_item()]}, ctx)
    assert err.value.code == "admin_only"
