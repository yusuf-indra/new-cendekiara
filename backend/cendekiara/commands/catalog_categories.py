"""catalog.categories: the exam categories for the public site."""

from __future__ import annotations

from cendekiara.core import plugins
from cendekiara.core.context import Context
from cendekiara.core.models import Model
from cendekiara.core.registry import Command, command


class CatalogCategoriesIn(Model):
    """No arguments."""


class CatalogExamBrief(Model):
    id: str
    name_key: str  # i18n key: exam.<id>.name
    status: str


class CatalogCategory(Model):
    id: str
    name_key: str  # i18n key: category.<id>.name
    exams: list[CatalogExamBrief]


class CatalogCategoriesOut(Model):
    categories: list[CatalogCategory]


@command(
    "catalog.categories",
    summary="The exam categories and the exams in each",
    readonly=True,
    public=True,
    cache_seconds=300,
)
class CatalogCategories(Command[CatalogCategoriesIn, CatalogCategoriesOut]):
    def run(self, args: CatalogCategoriesIn, ctx: Context) -> CatalogCategoriesOut:
        by_category: dict[str, list[CatalogExamBrief]] = {}
        for exam in plugins.all_exams():
            brief = CatalogExamBrief(
                id=exam.id,
                name_key=f"exam.{exam.id}.name",
                status=exam.status,
            )
            by_category.setdefault(exam.category, []).append(brief)

        categories = [
            CatalogCategory(
                id=category,
                name_key=f"category.{category}.name",
                exams=sorted(exams, key=lambda brief: brief.id),
            )
            for category, exams in sorted(by_category.items())
        ]
        return CatalogCategoriesOut(categories=categories)
