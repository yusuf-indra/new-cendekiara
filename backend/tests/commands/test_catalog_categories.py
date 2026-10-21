"""catalog.categories: public, readonly, cached, i18n keys (no brand strings)."""

from __future__ import annotations

from cendekiara.core import registry
from cendekiara.core.context import Context


def test_catalog_categories_lists_both_categories(guest_ctx: Context) -> None:
    out = registry.execute("catalog.categories", {}, guest_ctx)
    categories = out.model_dump()["categories"]
    assert {category["id"] for category in categories} == {"english", "seleksi-kedinasan"}


def test_catalog_categories_groups_the_exams(guest_ctx: Context) -> None:
    out = registry.execute("catalog.categories", {}, guest_ctx)
    categories = {category["id"]: category for category in out.model_dump()["categories"]}
    assert {exam["id"] for exam in categories["english"]["exams"]} == {"ielts", "toefl", "gmat"}
    assert {exam["id"] for exam in categories["seleksi-kedinasan"]["exams"]} == {
        "tpa-bappenas",
        "cpns-skd",
        "pkn-stan",
    }


def test_catalog_categories_is_public_readonly_and_cached() -> None:
    info = registry.get("catalog.categories")
    assert info.public is True
    assert info.readonly is True
    assert info.cache_seconds > 0


def test_catalog_categories_exposes_i18n_keys_not_brands(guest_ctx: Context) -> None:
    out = registry.execute("catalog.categories", {}, guest_ctx)
    for category in out.model_dump()["categories"]:
        assert category["name_key"] == f"category.{category['id']}.name"
        for exam in category["exams"]:
            assert exam["name_key"] == f"exam.{exam['id']}.name"
