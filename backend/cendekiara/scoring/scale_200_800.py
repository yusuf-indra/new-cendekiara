"""scale_200_800: a linear 200-800 score (a Bappenas-style estimate)."""

from __future__ import annotations

from cendekiara.core.plugins import RawResult, Score, TestSpec, scoring


@scoring("scale_200_800")
def score(result: RawResult, test: TestSpec) -> Score:
    """Estimate a 200-800 score: ``200 + 600 * raw/total``.

    This is an estimate, computed from the ratio of correct answers, not an
    official Bappenas score. `raw` is the marks of the section (one mark per
    correct question, minus the wrong penalty the core already applied), so a
    package with a wrong penalty scores lower. Each section is scaled the same
    way; the overall score uses the totals across all sections. An empty test
    scores 200.
    """
    correct = sum(section.correct for section in result.sections.values())
    wrong = sum(section.wrong for section in result.sections.values())
    blank = sum(section.blank for section in result.sections.values())
    raw = sum(section.marks for section in result.sections.values())
    total = sum(spec.total for spec in test.sections.values())

    def scale(value: float, size: int) -> float:
        if size <= 0:
            return 200.0
        return 200.0 + 600.0 * value / size

    sections = {
        section_id: scale(result.sections[section_id].marks, spec.total)
        for section_id, spec in test.sections.items()
        if section_id in result.sections
    }
    return Score(
        score=round(scale(raw, total)),
        score_type="number",
        sections=sections,
        correct=correct,
        wrong=wrong,
        blank=blank,
    )
