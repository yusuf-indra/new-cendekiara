"""job.get: only the creator or a current admin may read a job (never reveal existence)."""

from __future__ import annotations

import pytest

from cendekiara.core import clock, registry
from cendekiara.core.context import Context
from cendekiara.core.errors import AppError
from cendekiara.core.jobs import Job, JobActor
from cendekiara.core.store import MemoryStore, save

EXPORT_RESULT = {
    "count": 1,
    "items": [{"id": "tpa-test-1"}],
    "keys": [{"id": "tpa-test-1", "answers": {"q1": ["B"]}}],
}


def _make_job(mem: MemoryStore, creator: str, name: str = "bank.export") -> None:
    save(
        mem,
        "jobs",
        "j1",
        Job(
            id="j1",
            name=name,
            args={},
            actor=JobActor(uid=creator, email="admin@example.com" if creator == "u-admin" else None),
            created_by=creator,
            status="done",
            result=EXPORT_RESULT,
            created_at=clock.now_iso(),
        ),
    )


def test_job_get_is_readonly_and_not_public() -> None:
    info = registry.get("job.get")
    assert info.readonly is True
    assert info.public is False
    assert info.admin_only is False


def test_the_creator_reads_their_job(admin_ctx: Context) -> None:
    _make_job(admin_ctx.store, "u-admin")
    out = registry.execute("job.get", {"job_id": "j1"}, admin_ctx)
    data = out.model_dump()
    assert data["status"] == "done"
    assert data["result"]["keys"][0]["answers"] == {"q1": ["B"]}


def test_a_current_admin_reads_anothers_job(admin_ctx: Context) -> None:
    _make_job(admin_ctx.store, "someone-else")
    out = registry.execute("job.get", {"job_id": "j1"}, admin_ctx)
    assert out.model_dump()["status"] == "done"


def test_a_non_owner_student_cannot_read_an_export_job(ctx: Context) -> None:
    _make_job(ctx.store, "u-admin")
    with pytest.raises(AppError) as err:
        registry.execute("job.get", {"job_id": "j1"}, ctx)
    assert err.value.code == "not_found"


def test_a_missing_job_is_not_found(admin_ctx: Context) -> None:
    with pytest.raises(AppError) as err:
        registry.execute("job.get", {"job_id": "nope"}, admin_ctx)
    assert err.value.code == "not_found"


def test_job_get_needs_login(guest_ctx: Context) -> None:
    with pytest.raises(AppError) as err:
        registry.execute("job.get", {"job_id": "j1"}, guest_ctx)
    assert err.value.code == "login_required"
