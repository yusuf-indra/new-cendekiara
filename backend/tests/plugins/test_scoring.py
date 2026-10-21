"""The scoring plugins: scale_200_800 and ielts_band, table-driven."""

from __future__ import annotations

import pytest

from cendekiara.core.plugins import (
    RawResult,
    SectionResult,
    SectionSpec,
    TestSpec,
    get_scoring,
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
    result = RawResult(sections={"s": SectionResult(correct=correct)})
    test = TestSpec(sections={"s": SectionSpec(total=total)})
    assert get_scoring("scale_200_800")(result, test).score == expected


def test_scale_200_800_totals_across_sections() -> None:
    result = RawResult(
        sections={
            "verbal": SectionResult(correct=4, wrong=1),
            "kuantitatif": SectionResult(correct=6, blank=4),
        }
    )
    test = TestSpec(sections={"verbal": SectionSpec(total=5), "kuantitatif": SectionSpec(total=10)})
    out = get_scoring("scale_200_800")(result, test)
    assert out.score == 600  # 10 / 15 correct
    assert out.correct == 10
    assert out.wrong == 1
    assert out.blank == 4


def test_ielts_band_empty_is_zero() -> None:
    out = get_scoring("ielts_band")(RawResult(), TestSpec())
    assert out.score == 0.0
    assert out.score_type == "band"


def test_ielts_band_all_correct_is_nine() -> None:
    names = ("listening", "reading", "writing", "speaking")
    result = RawResult(sections={name: SectionResult(correct=40) for name in names})
    test = TestSpec(sections={name: SectionSpec(total=40) for name in names})
    assert get_scoring("ielts_band")(result, test).score == 9.0


def test_ielts_band_scales_a_short_test_to_40() -> None:
    result = RawResult(sections={"listening": SectionResult(correct=10)})
    test = TestSpec(sections={"listening": SectionSpec(total=10)})
    assert get_scoring("ielts_band")(result, test).score == 9.0


@pytest.mark.parametrize(
    ("correct", "expected"),
    [(40, 9.0), (35, 8.0), (30, 7.0), (23, 6.0), (16, 5.0), (0, 0.0)],
)
def test_ielts_band_estimate_table(correct: int, expected: float) -> None:
    result = RawResult(sections={"listening": SectionResult(correct=correct)})
    test = TestSpec(sections={"listening": SectionSpec(total=40)})
    assert get_scoring("ielts_band")(result, test).score == expected
