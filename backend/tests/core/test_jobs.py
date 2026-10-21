"""The job lifecycle, the actor re-check, the JOBS modes and the worker token."""

from __future__ import annotations

import pytest

from cendekiara.core import clock, jobs
from cendekiara.core.config import Settings
from cendekiara.core.context import Actor, Context
from cendekiara.core.errors import AppError
from cendekiara.core.jobs import Job, JobActor
from cendekiara.core.store import MemoryStore, save


def _admin_ctx(mem: MemoryStore, settings: Settings) -> Context:
    return Context(Actor(uid="u-admin", email="admin@example.com", is_admin=True), mem, settings=settings)


def _queued_job(name: str, args: dict, email: str = "admin@example.com") -> Job:
    return Job(
        id="j1",
        name=name,
        args=args,
        actor=JobActor(uid="u-admin", email=email),
        created_by="u-admin",
        status="queued",
        created_at=clock.now_iso(),
    )


def test_enqueue_stores_the_identity_and_dispatches(
    mem: MemoryStore, jobs_settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(jobs, "_dispatch", lambda *a, **k: None)
    job_id = jobs.enqueue("bank.export", {}, _admin_ctx(mem, jobs_settings))
    doc = mem.get("jobs", job_id)
    assert doc is not None
    assert doc["status"] == "queued"
    assert doc["actor"] == {"uid": "u-admin", "email": "admin@example.com"}
    assert doc["createdBy"] == "u-admin"
    assert "isAdmin" not in doc  # never store an admin flag


def test_run_job_stores_the_result(mem: MemoryStore, jobs_settings: Settings) -> None:
    save(mem, "jobs", "j1", _queued_job("bank.export", {}))
    jobs.run_job("j1", mem, jobs_settings, "id")
    doc = mem.get("jobs", "j1")
    assert doc is not None
    assert doc["status"] == "done"
    assert doc["result"]["count"] == 0  # type: ignore[index]


def test_run_job_captures_a_failure(mem: MemoryStore, jobs_settings: Settings) -> None:
    save(mem, "jobs", "j1", _queued_job("catalog.exam", {"exam_id": "nope"}))
    jobs.run_job("j1", mem, jobs_settings, "id")
    doc = mem.get("jobs", "j1")
    assert doc is not None
    assert doc["status"] == "failed"
    assert doc["error"]["code"] == "not_found"  # type: ignore[index]


def test_run_job_rechecks_admin_at_run_time(mem: MemoryStore, jobs_settings: Settings) -> None:
    """A job enqueued by an admin fails once that email is no longer an admin."""
    save(mem, "jobs", "j1", _queued_job("bank.export", {}))
    demoted = Settings(_env_file=None, app_env="dev", jobs="inline", admin_emails=[])
    jobs.run_job("j1", mem, demoted, "id")
    doc = mem.get("jobs", "j1")
    assert doc is not None
    assert doc["status"] == "failed"
    assert doc["error"]["code"] == "admin_only"  # type: ignore[index]


def test_run_job_skips_a_non_queued_job(mem: MemoryStore, jobs_settings: Settings) -> None:
    done = _queued_job("bank.export", {})
    done.status = "done"
    save(mem, "jobs", "j1", done)
    jobs.run_job("j1", mem, jobs_settings, "id")
    assert mem.get("jobs", "j1")["status"] == "done"  # type: ignore[index]


def test_run_job_ignores_a_missing_job(mem: MemoryStore, jobs_settings: Settings) -> None:
    jobs.run_job("nope", mem, jobs_settings, "id")  # must not raise


def test_enqueue_inline_dispatches_a_thread(
    mem: MemoryStore, jobs_settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    seen: dict[str, str] = {}
    monkeypatch.setattr(jobs, "_run_inline", lambda jid, store, s, site: seen.update(jid=jid))
    job_id = jobs.enqueue("bank.export", {}, _admin_ctx(mem, jobs_settings))
    assert seen["jid"] == job_id


def test_enqueue_cloudtasks_enqueues_a_task(mem: MemoryStore, monkeypatch: pytest.MonkeyPatch) -> None:
    settings = Settings(
        _env_file=None,
        app_env="dev",
        jobs="cloudtasks",
        worker_url="https://worker.test",
        tasks_service_account="worker@svc.test",
        tasks_queue="projects/p/locations/l/queues/q",
    )
    seen: dict[str, str] = {}
    monkeypatch.setattr(jobs, "_enqueue_cloud_task", lambda jid, s: seen.update(jid=jid))
    job_id = jobs.enqueue("bank.export", {}, _admin_ctx(mem, settings))
    assert seen["jid"] == job_id


def _worker_settings() -> Settings:
    return Settings(
        _env_file=None,
        app_env="dev",
        jobs="cloudtasks",
        worker_url="https://worker.test",
        tasks_service_account="worker@svc.test",
    )


def _fake_verifier(claims: dict) -> jobs.WorkerVerifier:
    def verify(token: str, settings: Settings) -> dict:
        return claims

    return verify


def test_verify_worker_token_accepts_the_right_claims() -> None:
    settings = _worker_settings()
    verifier = _fake_verifier({"aud": "https://worker.test", "email": "worker@svc.test"})
    assert jobs.verify_worker_token("tok", settings, verifier) == "worker@svc.test"


def test_verify_worker_token_rejects_a_wrong_audience() -> None:
    settings = _worker_settings()
    verifier = _fake_verifier({"aud": "https://evil.test", "email": "worker@svc.test"})
    with pytest.raises(AppError) as err:
        jobs.verify_worker_token("tok", settings, verifier)
    assert err.value.code == "invalid_token"


def test_verify_worker_token_rejects_a_wrong_email() -> None:
    settings = _worker_settings()
    verifier = _fake_verifier({"aud": "https://worker.test", "email": "other@svc.test"})
    with pytest.raises(AppError) as err:
        jobs.verify_worker_token("tok", settings, verifier)
    assert err.value.code == "invalid_token"


def test_verify_worker_token_rejects_a_broken_token() -> None:
    def boom(token: str, settings: Settings) -> dict:
        raise ValueError("bad signature")

    with pytest.raises(AppError) as err:
        jobs.verify_worker_token("tok", _worker_settings(), boom)
    assert err.value.code == "invalid_token"
