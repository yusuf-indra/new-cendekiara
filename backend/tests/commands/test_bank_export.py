"""bank.export: queued admin dump of items + keys, stored in the job result."""

from __future__ import annotations

import pytest

from cendekiara.core import jobs, registry
from cendekiara.core.config import Settings
from cendekiara.core.context import Actor, Context
from cendekiara.core.errors import AppError
from cendekiara.core.store import MemoryStore
from tests.item_helpers import make_item, make_key


def test_bank_export_is_queued_and_admin() -> None:
    info = registry.get("bank.export")
    assert info.queued is True
    assert info.admin_only is True


def test_bank_export_returns_items_and_keys(mem: MemoryStore, jobs_settings: Settings) -> None:
    mem.set("items", "tpa-test-1", make_item())
    mem.set("item_keys", "tpa-test-1", make_key())
    ctx = Context(Actor(uid="u-admin", email="admin@example.com", is_admin=True), mem, settings=jobs_settings)
    out = registry.execute("bank.export", {}, ctx)
    jobs.run_job(out.job_id, mem, jobs_settings, "id")
    result = mem.get("jobs", out.job_id)["result"]  # type: ignore[index]
    assert result["count"] == 1
    assert result["items"][0]["id"] == "tpa-test-1"
    assert result["keys"][0]["answers"] == {"q1": ["B"]}


def test_bank_export_can_filter_by_exam(mem: MemoryStore, jobs_settings: Settings) -> None:
    mem.set("items", "tpa-test-1", make_item())
    mem.set("items", "ielts-1", make_item(item_id="ielts-1", exam="ielts", section="reading"))
    ctx = Context(Actor(uid="u-admin", email="admin@example.com", is_admin=True), mem, settings=jobs_settings)
    out = registry.execute("bank.export", {"exam": "ielts"}, ctx)
    jobs.run_job(out.job_id, mem, jobs_settings, "id")
    result = mem.get("jobs", out.job_id)["result"]  # type: ignore[index]
    assert result["count"] == 1
    assert result["items"][0]["id"] == "ielts-1"


def test_bank_export_needs_admin(ctx: Context) -> None:
    with pytest.raises(AppError) as err:
        registry.execute("bank.export", {}, ctx)
    assert err.value.code == "admin_only"
