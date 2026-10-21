"""catalog.tests: the active packages of an exam. No item ids, no content, no keys."""

from __future__ import annotations

from pydantic import Field

from cendekiara.core import plugins
from cendekiara.core.context import Context
from cendekiara.core.items import Test
from cendekiara.core.models import Model
from cendekiara.core.registry import Command, command


class CatalogTestsIn(Model):
    exam_id: str = Field(description="Exam id, e.g. 'tpa-bappenas'")


class CatalogTestSection(Model):
    id: str
    count: int  # how many items the section has (never their ids)


class CatalogTestBrief(Model):
    id: str
    exam: str
    status: str
    free: bool
    duration_sec: int | None = None
    sections: list[CatalogTestSection]


class CatalogTestsOut(Model):
    tests: list[CatalogTestBrief]


@command(
    "catalog.tests",
    summary="The active packages of an exam (no item ids or keys)",
    readonly=True,
    public=True,
    cache_seconds=300,
)
class CatalogTests(Command[CatalogTestsIn, CatalogTestsOut]):
    def run(self, args: CatalogTestsIn, ctx: Context) -> CatalogTestsOut:
        plugins.get_exam(args.exam_id)  # unknown exam -> not_found
        rows = ctx.store.list("tests", {"exam": args.exam_id}, limit=1000)
        tests: list[CatalogTestBrief] = []
        for row in rows:
            test = Test.from_doc(row)
            if test.status != "active":
                continue
            tests.append(
                CatalogTestBrief(
                    id=test.id,
                    exam=test.exam,
                    status=test.status,
                    free=test.free,
                    duration_sec=test.duration_sec,
                    sections=[
                        CatalogTestSection(id=section_id, count=len(item_ids))
                        for section_id, item_ids in test.sections.items()
                    ],
                )
            )
        tests.sort(key=lambda brief: brief.id)
        return CatalogTestsOut(tests=tests)
