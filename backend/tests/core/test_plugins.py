"""Plugin discovery: the six exams, the two scoring methods, the four question types."""

from __future__ import annotations

import pytest

from cendekiara.core import plugins
from cendekiara.core.errors import AppError
from cendekiara.core.plugins import ExamDef

EXAM_IDS = {"ielts", "tpa-bappenas", "cpns-skd", "pkn-stan", "toefl", "gmat"}


def test_all_exams_are_discovered() -> None:
    assert {exam.id for exam in plugins.all_exams()} == EXAM_IDS


def test_scoring_plugins_are_discovered() -> None:
    assert set(plugins.all_scoring()) == {"scale_200_800", "ielts_band"}


def test_qtype_plugins_are_discovered() -> None:
    assert set(plugins.all_qtypes()) == {"choice", "select", "multi", "text"}


def test_exam_categories_are_english_and_seleksi_kedinasan() -> None:
    assert {exam.category for exam in plugins.all_exams()} == {"english", "seleksi-kedinasan"}


def test_get_exam_unknown_is_not_found() -> None:
    with pytest.raises(AppError) as err:
        plugins.get_exam("nope")
    assert err.value.code == "not_found"


def test_a_dummy_exam_registers_without_editing_core(monkeypatch: pytest.MonkeyPatch) -> None:
    dummy = ExamDef(
        id="dummy-exam",
        category="english",
        scoring="scale_200_800",
        layout="cbt",
        content_lang="en",
        status="coming_soon",
        sections={"verbal": ("analogy",)},
        sites=("global",),
    )
    plugins.register_exam(dummy)
    assert plugins.get_exam("dummy-exam") is dummy
    # Remove the test-only exam so it does not leak into other tests.
    monkeypatch.delitem(plugins._EXAMS, "dummy-exam")  # type: ignore[attr-defined]
