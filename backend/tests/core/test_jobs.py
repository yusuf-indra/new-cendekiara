"""The job lifecycle, the actor re-check, the JOBS modes and the worker token."""

from __future__ import annotations

import json
import logging
import sys
from types import ModuleType, SimpleNamespace

import pytest

from cendekiara.core import clock, jobs, registry
from cendekiara.core.config import Settings
from cendekiara.core.context import Actor, Context
from cendekiara.core.errors import AppError
from cendekiara.core.jobs import Job, JobActor
from cendekiara.core.models import Model
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


class _RecordingStore(MemoryStore):
    """A store that remembers every status a job went through."""

    def __init__(self, seed: dict | None = None) -> None:
        super().__init__(seed)
        self.statuses: list[str] = []

    def update(self, collection: str, doc_id: str, fields: dict) -> None:
        super().update(collection, doc_id, fields)
        if collection == "jobs" and "status" in fields:
            self.statuses.append(fields["status"])


def test_run_job_fails_a_job_with_invalid_stored_args(jobs_settings: Settings) -> None:
    """Stored arguments that do not fit the command fail with invalid_args."""
    mem = _RecordingStore()
    save(mem, "jobs", "j1", _queued_job("catalog.exam", {"exam_id": 123}))
    jobs.run_job("j1", mem, jobs_settings, "id")
    doc = mem.get("jobs", "j1")
    assert doc is not None
    assert doc["status"] == "failed"
    assert doc["error"]["code"] == "invalid_args"  # type: ignore[index]
    assert "123" not in doc["error"]["message"]  # type: ignore[index]
    assert mem.statuses[-1] == "failed"


class _BoomIn(Model):
    count: int = 0


class _BoomOut(Model):
    ok: bool = True


class _BoomCommand(registry.Command[_BoomIn, _BoomOut]):
    """A command with a bug: it raises something that is not an AppError."""

    input_model = _BoomIn
    output_model = _BoomOut

    def run(self, args: _BoomIn, ctx: Context) -> _BoomOut:
        raise RuntimeError("boom")


def test_run_job_fails_a_job_that_raises(
    jobs_settings: Settings, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """A bug in a command fails the job; it is never left running."""
    info = registry.CommandInfo(
        name="test.boom",
        summary="raises",
        queued=False,
        admin_only=False,
        allow_jobs=True,
        readonly=False,
        public=False,
        cache_seconds=0,
        cls=_BoomCommand,
    )
    monkeypatch.setattr(registry, "get", lambda name: info)
    mem = _RecordingStore()
    save(mem, "jobs", "j1", _queued_job("test.boom", {}))
    with caplog.at_level(logging.ERROR):
        jobs.run_job("j1", mem, jobs_settings, "id")
    doc = mem.get("jobs", "j1")
    assert doc is not None
    assert doc["status"] == "failed"
    assert doc["error"]["code"] == "internal_error"  # type: ignore[index]
    assert doc["error"]["message"] == "The job failed unexpectedly"  # type: ignore[index]
    assert "boom" not in json.dumps(doc["error"])  # no traceback, no internal message
    assert doc["finishedAt"] is not None
    assert mem.statuses[-1] == "failed"  # never left "running"
    assert any(record.exc_info for record in caplog.records)  # logged server-side


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


class _FakeOidcToken:
    def __init__(self, service_account_email: str, audience: str | None = None) -> None:
        self.service_account_email = service_account_email
        self.audience = audience


class _FakeHttpRequest:
    def __init__(self, http_method: str, url: str, oidc_token: _FakeOidcToken, body: bytes) -> None:
        self.http_method = http_method
        self.url = url
        self.oidc_token = oidc_token
        self.body = body


class _FakeTask:
    def __init__(self, http_request: _FakeHttpRequest) -> None:
        self.http_request = http_request


class _FakeCreateTaskRequest:
    def __init__(self, parent: str, task: _FakeTask) -> None:
        self.parent = parent
        self.task = task


def _fake_tasks_module() -> tuple[ModuleType, list[_FakeCreateTaskRequest]]:
    """A stand-in for google.cloud.tasks_v2 (not installed in the test venv)."""
    module = ModuleType("google.cloud.tasks_v2")
    created: list[_FakeCreateTaskRequest] = []

    class _Client:
        def create_task(self, request: _FakeCreateTaskRequest) -> None:
            created.append(request)

    module.CloudTasksClient = _Client  # type: ignore[attr-defined]
    module.CreateTaskRequest = _FakeCreateTaskRequest  # type: ignore[attr-defined]
    module.Task = _FakeTask  # type: ignore[attr-defined]
    module.HttpRequest = _FakeHttpRequest  # type: ignore[attr-defined]
    module.HttpMethod = SimpleNamespace(POST="POST")  # type: ignore[attr-defined]
    module.OidcToken = _FakeOidcToken  # type: ignore[attr-defined]
    return module, created


def test_enqueue_cloud_task_sets_the_oidc_audience(monkeypatch: pytest.MonkeyPatch) -> None:
    """The task must ask for the worker URL as audience, not the task URL."""
    settings = Settings(
        _env_file=None,
        app_env="dev",
        jobs="cloudtasks",
        worker_url="https://worker.test",
        tasks_service_account="worker@svc.test",
        tasks_queue="projects/p/locations/l/queues/q",
    )
    module, created = _fake_tasks_module()
    monkeypatch.setitem(sys.modules, "google.cloud.tasks_v2", module)
    jobs._enqueue_cloud_task("j1", settings)
    assert len(created) == 1
    http_request = created[0].task.http_request
    assert http_request.oidc_token.audience == settings.worker_url
    assert http_request.oidc_token.service_account_email == settings.tasks_service_account
    assert http_request.url == "https://worker.test/internal/jobs/run"
    assert http_request.url.endswith("/internal/jobs/run")


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


def test_google_verify_uses_the_worker_url_as_audience(monkeypatch: pytest.MonkeyPatch) -> None:
    """The token is verified for the same audience the task asks for."""
    settings = _worker_settings()
    requests_module = ModuleType("google.auth.transport.requests")
    id_token_module = ModuleType("google.oauth2.id_token")
    seen: dict[str, object] = {}

    class _Request:
        pass

    def verify_token(token: str, request: object = None, audience: str | None = None) -> dict:
        seen["audience"] = audience
        return {"aud": audience, "email": settings.tasks_service_account}

    requests_module.Request = _Request  # type: ignore[attr-defined]
    id_token_module.verify_token = verify_token  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "google.auth.transport.requests", requests_module)
    monkeypatch.setitem(sys.modules, "google.oauth2.id_token", id_token_module)
    claims = jobs._google_verify("tok", settings)
    assert seen["audience"] == settings.worker_url
    assert claims["aud"] == settings.worker_url
