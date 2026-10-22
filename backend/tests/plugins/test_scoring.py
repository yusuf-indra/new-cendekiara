"""The scoring plugins: scale_200_800 and ielts_band, table-driven.

The score is computed from the marks of the section (one mark per correct
question); the core applies the wrong penalty to the marks before the plugin
runs (docs/04-exams.md).
"""

from __future__ import annotations

import pytest

from cendekiara.core.plugins import (
    RawResult,
    SectionResult,
    SectionSpec,
    TestSpec,
    get_scoring,
)


def section(correct: int, wrong: int = 0, blank: int = 0, marks: float | None = None) -> SectionResult:
    """A section result: the marks are the correct answers, unless given."""
    return SectionResult(
        correct=correct,
        wrong=wrong,
        blank=blank,
        marks=float(correct) if marks is None else marks,
    )


def test_scale_200_800_empty_is_the_bottom_of_the_scale() -> None:
    out = get_scoring("scale_200_800")(RawResult(), TestSpec())
    assert out.score == 200
    assert out.score_type == "number"


@pytest.mark.parametrize(
    ("correct", "total", "expected"),
    [(0, 10, 200), (5, 10, 500), (10, 10, 800)],
)
def test_scale_200_800_is_linear(correct: int, total: int, expected: int) -> None:
    result = RawResult(sections={"s": section(correct)})
    test = TestSpec(sections={"s": SectionSpec(total=total)})
    assert get_scoring("scale_200_800")(result, test).score == expected


def test_scale_200_800_totals_across_sections() -> None:
    result = RawResult(
        sections={
            "verbal": section(4, wrong=1),
            "kuantitatif": section(6, blank=4),
        }
    )
    test = TestSpec(sections={"verbal": SectionSpec(total=5), "kuantitatif": SectionSpec(total=10)})
    out = get_scoring("scale_200_800")(result, test)
    assert out.score == 600  # 10 / 15 correct
    assert out.correct == 10
    assert out.wrong == 1
    assert out.blank == 4


def test_scale_200_800_uses_the_marks_of_the_wrong_penalty() -> None:
    """The penalty the core applied lowers the score (the marks are lower)."""
    result = RawResult(sections={"s": section(4, wrong=1, marks=3.5)})
    test = TestSpec(sections={"s": SectionSpec(total=10)})
    out = get_scoring("scale_200_800")(result, test)
    assert out.score == 410  # 200 + 600 * 3.5 / 10
    assert out.correct == 4  # the count of correct answers never changes


def test_ielts_band_empty_is_zero() -> None:
    out = get_scoring("ielts_band")(RawResult(), TestSpec())
    assert out.score == 0.0
    assert out.score_type == "band"


def test_ielts_band_all_correct_is_nine() -> None:
    names = ("listening", "reading", "writing", "speaking")
    result = RawResult(sections={name: section(40) for name in names})
    test = TestSpec(sections={name: SectionSpec(total=40) for name in names})
    assert get_scoring("ielts_band")(result, test).score == 9.0


def test_ielts_band_scales_a_short_test_to_40() -> None:
    result = RawResult(sections={"listening": section(10)})
    test = TestSpec(sections={"listening": SectionSpec(total=10)})
    assert get_scoring("ielts_band")(result, test).score == 9.0


@pytest.mark.parametrize(
    ("correct", "expected"),
    [(40, 9.0), (35, 8.0), (30, 7.0), (23, 6.0), (16, 5.0), (0, 0.0)],
)
def test_ielts_band_estimate_table(correct: int, expected: float) -> None:
    result = RawResult(sections={"listening": section(correct)})
    test = TestSpec(sections={"listening": SectionSpec(total=40)})
    assert get_scoring("ielts_band")(result, test).score == expected
