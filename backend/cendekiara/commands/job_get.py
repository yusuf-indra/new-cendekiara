"""job.get: the status and result of a queued job. Creator or a current admin only."""

from __future__ import annotations

from typing import Any

from pydantic import Field

from cendekiara.core.context import Context
from cendekiara.core.errors import AppError
from cendekiara.core.jobs import Job
from cendekiara.core.models import Model
from cendekiara.core.registry import Command, command


class JobGetIn(Model):
    job_id: str = Field(description="The id returned by a queued command")


class JobGetOut(Model):
    id: str
    name: str
    status: str
    result: dict[str, Any] | None = None
    error: dict[str, str | None] | None = None
    created_at: str
    started_at: str | None = None
    finished_at: str | None = None


@command("job.get", summary="The status and result of a queued job", readonly=True)
class JobGet(Command[JobGetIn, JobGetOut]):
    def run(self, args: JobGetIn, ctx: Context) -> JobGetOut:
        uid = ctx.actor.require_uid()
        doc = ctx.store.get("jobs", args.job_id)
        if doc is None:
            raise AppError("not_found", f"jobs/{args.job_id} not found")
        job = Job.from_doc(doc)
        # Ownership: only the creator or a current admin may read the result.
        if job.created_by != uid and not ctx.actor.is_admin:
            raise AppError("not_found", f"jobs/{args.job_id} not found")
        return JobGetOut(
            id=job.id,
            name=job.name,
            status=job.status,
            result=job.result,
            error=job.error,
            created_at=job.created_at,
            started_at=job.started_at,
            finished_at=job.finished_at,
        )
