"""Queued commands: the job document, enqueueing, and the worker that runs a job.

A queued command returns ``{jobId}`` at once and the worker runs it later.
`enqueue` stores the caller's identity (uid + email, never a stored admin
flag); `run_job` recomputes admin from the settings at run time, so a demoted
admin's queued job fails with `admin_only` (docs/10-security.md rule 5, the
Phase 3 decision A). Locally (`JOBS=inline`) a job runs in a background
thread; in production (`JOBS=cloudtasks`) it is enqueued to Cloud Tasks.

A job always ends: `done` or `failed`. A bad argument fails with
`invalid_args`, a bug in a command with `internal_error` (the traceback stays
in the server log, never in the job document).
"""

from __future__ import annotations

import importlib
import json
import logging
import threading
import uuid
from collections.abc import Callable, Mapping
from typing import Any, Literal, cast

from pydantic import ValidationError

from cendekiara.core import clock, config
from cendekiara.core import store as store_mod
from cendekiara.core.context import Actor, Context
from cendekiara.core.errors import AppError
from cendekiara.core.models import Model
from cendekiara.core.store import Store

log = logging.getLogger(__name__)

JobStatus = Literal["queued", "running", "done", "failed"]

COLLECTION = "jobs"


class JobActor(Model):
    """The identity of the caller who queued a job. No admin flag: it is re-checked."""

    uid: str
    email: str | None = None


class Job(Model):
    """`jobs/{jobId}`: a queued command and its outcome."""

    id: str
    name: str
    args: dict[str, Any]
    actor: JobActor
    created_by: str  # the uid, repeated at top level for simple ownership checks
    status: JobStatus = "queued"
    result: dict[str, Any] | None = None
    error: dict[str, str | None] | None = None
    created_at: str
    started_at: str | None = None
    finished_at: str | None = None


class JobQueuedOut(Model):
    """What a queued command returns immediately; poll `job.get` for the result."""

    job_id: str


def new_job_id() -> str:
    """A unique job id."""
    return uuid.uuid4().hex


def enqueue(name: str, args: dict[str, Any], ctx: Context) -> str:
    """Create the job and dispatch it; returns the job id.

    The caller's access was already checked by `registry.execute` before this
    call. The identity is stored as ``{uid, email}`` only, never an admin flag.
    """
    settings = ctx.settings or config.settings
    uid = ctx.actor.require_uid()
    job = Job(
        id=new_job_id(),
        name=name,
        args=args,
        actor=JobActor(uid=uid, email=ctx.actor.email),
        created_by=uid,
        status="queued",
        created_at=clock.now_iso(),
    )
    store_mod.save(ctx.store, COLLECTION, job.id, job)
    ctx.log.info("job queued: %s (%s)", job.id, name)
    _dispatch(job.id, ctx.store, settings, ctx.site)
    return job.id


def _dispatch(job_id: str, store: Store, settings: config.Settings, site: str) -> None:
    """Run the job now (inline thread) or hand it to Cloud Tasks."""
    if settings.jobs == "inline":
        _run_inline(job_id, store, settings, site)
    else:
        _enqueue_cloud_task(job_id, settings)


def _run_inline(job_id: str, store: Store, settings: config.Settings, site: str) -> None:
    """Run the job in a background thread (local development)."""
    threading.Thread(target=run_job, args=(job_id, store, settings, site), daemon=True).start()


def run_job(job_id: str, store: Store, settings: config.Settings, site: str) -> None:
    """The worker: run one queued job, storing its result or its error.

    Admin is recomputed from `settings.is_admin_email(actor.email)` here, at
    run time — a job enqueued by someone who is no longer an admin fails.

    Every failure ends the job: a bad argument fails with `invalid_args`, a bug
    in a command fails with `internal_error` (the traceback stays in the server
    log, never in the job document). A job is never left "running".
    """
    from cendekiara.core import registry

    doc = store.get(COLLECTION, job_id)
    if doc is None:
        return
    try:
        job = Job.from_doc(doc)
    except ValidationError:
        log.exception("job document is invalid: %s", job_id)
        _fail_job(store, job_id, AppError("internal_error", "The job failed unexpectedly"))
        return
    if job.status != "queued":
        return
    store.update(COLLECTION, job_id, {"status": "running", "startedAt": clock.now_iso()})
    actor = Actor(
        uid=job.actor.uid,
        email=job.actor.email,
        is_admin=settings.is_admin_email(job.actor.email),
    )
    ctx = Context(actor, store, site=site, via="job", job_id=job_id, settings=settings)
    try:
        info = registry.get(job.name)
        registry.check_access(info, ctx)  # admin_only re-checked against the current email
        args = info.cls.input_model.model_validate(job.args)
        result = info.cls().run(args, ctx)
        store.update(
            COLLECTION,
            job_id,
            {"status": "done", "result": result.to_doc(), "finishedAt": clock.now_iso()},
        )
    except AppError as exc:
        _fail_job(store, job_id, exc)
    except ValidationError as exc:
        _fail_job(store, job_id, AppError("invalid_args", _invalid_args_message(job.name, exc)))
    except Exception:
        # A bug in a command: the job fails, the traceback stays in the log.
        log.exception("job failed unexpectedly: %s (%s)", job_id, job.name)
        _fail_job(store, job_id, AppError("internal_error", "The job failed unexpectedly"))


def _fail_job(store: Store, job_id: str, error: AppError) -> None:
    """Store the error of a job; the job is never left "running"."""
    store.update(
        COLLECTION,
        job_id,
        {"status": "failed", "error": error.to_dict(), "finishedAt": clock.now_iso()},
    )
    log.info("job failed: %s (%s)", job_id, error.code)


def _invalid_args_message(name: str, exc: ValidationError) -> str:
    """Why the stored arguments are invalid: the fields and the kinds of error.

    Never the values: the arguments of a command may hold answer keys.
    """
    reasons = sorted(
        {f"{'.'.join(str(part) for part in err['loc']) or 'args'}: {err['type']}" for err in exc.errors()}
    )
    return f"The arguments of {name} are invalid ({'; '.join(reasons)})"


WorkerVerifier = Callable[[str, config.Settings], Mapping[str, Any]]


def verify_worker_token(
    token: str,
    settings: config.Settings,
    verifier: WorkerVerifier | None = None,
) -> str:
    """Verify the OIDC token of a worker request; returns the service-account email.

    The token must carry the configured worker URL as audience and the
    configured tasks service account as its email, else `invalid_token`.
    `verifier` is injectable so tests run without Google credentials.
    """
    check = verifier or _google_verify
    try:
        claims = check(token, settings)
    except AppError:
        raise
    except Exception as exc:
        raise AppError("invalid_token", "The worker token could not be verified") from exc
    if claims.get("aud") != settings.worker_url:
        raise AppError("invalid_token", "The worker token has the wrong audience")
    email = claims.get("email")
    if not isinstance(email, str) or not email or email != settings.tasks_service_account:
        raise AppError("invalid_token", "The worker token is not for this service account")
    return email


def _google_verify(token: str, settings: config.Settings) -> Mapping[str, Any]:
    """Verify a Google-signed OIDC token (google-auth, imported lazily)."""
    requests = cast(Any, importlib.import_module("google.auth.transport.requests"))
    id_token = cast(Any, importlib.import_module("google.oauth2.id_token"))
    return cast(
        Mapping[str, Any],
        id_token.verify_token(token, request=requests.Request(), audience=settings.worker_url),
    )


def _enqueue_cloud_task(job_id: str, settings: config.Settings) -> None:
    """Create a Cloud Tasks task that POSTs ``{jobId}`` to the worker endpoint."""
    tasks = cast(Any, importlib.import_module("google.cloud.tasks_v2"))
    client = tasks.CloudTasksClient()
    path = f"{settings.worker_url.rstrip('/')}/internal/jobs/run"
    body = json.dumps({"jobId": job_id}).encode("utf-8")
    request = tasks.CreateTaskRequest(
        parent=settings.tasks_queue,
        task=tasks.Task(
            http_request=tasks.HttpRequest(
                http_method=tasks.HttpMethod.POST,
                url=path,
                oidc_token=tasks.OidcToken(service_account_email=settings.tasks_service_account),
                body=body,
            )
        ),
    )
    client.create_task(request=request)
