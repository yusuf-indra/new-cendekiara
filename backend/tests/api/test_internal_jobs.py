"""The /internal/jobs/run worker endpoint: mounted only for cloudtasks, OIDC-guarded."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from cendekiara.api.app import create_app
from cendekiara.core import clock, jobs
from cendekiara.core.config import Settings
from cendekiara.core.jobs import Job, JobActor
from cendekiara.core.store import MemoryStore, save


def _cloud_settings() -> Settings:
    return Settings(
        _env_file=None,
        app_env="dev",
        site="id",
        store="memory",
        auth_mode="dev",
        jobs="cloudtasks",
        admin_emails=["admin@example.com"],
        worker_url="https://worker.test",
        tasks_service_account="worker@svc.test",
    )


def _queued_job() -> Job:
    return Job(
        id="j1",
        name="bank.export",
        args={},
        actor=JobActor(uid="u-admin", email="admin@example.com"),
        created_by="u-admin",
        status="queued",
        created_at=clock.now_iso(),
    )


def test_internal_endpoint_is_absent_when_jobs_is_inline(api_client: TestClient) -> None:
    response = api_client.post("/internal/jobs/run", json={"jobId": "j1"})
    assert response.status_code == 404


def test_internal_endpoint_runs_a_job_with_a_valid_token(
    mem: MemoryStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    save(mem, "jobs", "j1", _queued_job())
    monkeypatch.setattr(
        jobs, "_google_verify", lambda token, s: {"aud": "https://worker.test", "email": "worker@svc.test"}
    )
    client = TestClient(create_app(store=mem, settings=_cloud_settings()))
    response = client.post(
        "/internal/jobs/run",
        json={"jobId": "j1"},
        headers={"Authorization": "Bearer tok"},
    )
    assert response.status_code == 200
    assert mem.get("jobs", "j1")["status"] == "done"  # type: ignore[index]


def test_internal_endpoint_rejects_a_wrong_audience(
    mem: MemoryStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        jobs, "_google_verify", lambda token, s: {"aud": "https://evil.test", "email": "worker@svc.test"}
    )
    client = TestClient(create_app(store=mem, settings=_cloud_settings()))
    response = client.post(
        "/internal/jobs/run",
        json={"jobId": "j1"},
        headers={"Authorization": "Bearer tok"},
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "invalid_token"


def test_internal_endpoint_rejects_a_wrong_email(mem: MemoryStore, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        jobs, "_google_verify", lambda token, s: {"aud": "https://worker.test", "email": "other@svc.test"}
    )
    client = TestClient(create_app(store=mem, settings=_cloud_settings()))
    response = client.post(
        "/internal/jobs/run",
        json={"jobId": "j1"},
        headers={"Authorization": "Bearer tok"},
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "invalid_token"


def test_internal_endpoint_requires_a_token(mem: MemoryStore, monkeypatch: pytest.MonkeyPatch) -> None:
    client = TestClient(create_app(store=mem, settings=_cloud_settings()))
    response = client.post("/internal/jobs/run", json={"jobId": "j1"})
    assert response.status_code == 401
