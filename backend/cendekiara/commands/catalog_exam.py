"""catalog.exam: one exam's public definition (never the answer key)."""

from __future__ import annotations

from pydantic import Field

from cendekiara.core import plugins
from cendekiara.core.context import Context
from cendekiara.core.models import Model
from cendekiara.core.registry import Command, command


class CatalogExamIn(Model):
    exam_id: str = Field(description="Exam id, e.g. 'tpa-bappenas'")


class CatalogExamSection(Model):
    id: str
    name_key: str  # i18n key: section.<exam>.<section>
    topics: list[str]  # topic slugs (i18n key: topic.<topic>)


class CatalogExamOut(Model):
    id: str
    category: str
    scoring: str
    layout: str
    content_lang: str
    features: list[str]
    status: str
    sites: list[str]
    name_key: str  # i18n key: exam.<id>.name
    description_key: str  # i18n key: exam.<id>.description
    sections: list[CatalogExamSection]


@command(
    "catalog.exam",
    summary="One exam's public definition (sections and topics, no answers)",
    readonly=True,
    public=True,
    cache_seconds=300,
)
class CatalogExam(Command[CatalogExamIn, CatalogExamOut]):
    def run(self, args: CatalogExamIn, ctx: Context) -> CatalogExamOut:
        exam = plugins.get_exam(args.exam_id)  # unknown id -> not_found
        sections = [
            CatalogExamSection(
                id=section_id,
                name_key=f"section.{exam.id}.{section_id}",
                topics=list(topics),
            )
            for section_id, topics in exam.sections.items()
        ]
        return CatalogExamOut(
            id=exam.id,
            category=exam.category,
            scoring=exam.scoring,
            layout=exam.layout,
            content_lang=exam.content_lang,
            features=list(exam.features),
            status=exam.status,
            sites=list(exam.sites),
            name_key=f"exam.{exam.id}.name",
            description_key=f"exam.{exam.id}.description",
            sections=sections,
        )
