"""ielts_band: an IELTS-style band estimate from our own table."""

from __future__ import annotations

import math

from cendekiara.core.plugins import RawResult, Score, TestSpec, scoring

# Our own estimate of how many correct answers (out of 40) map to each band.
# Original wording and cutoffs, not the official band descriptors.
_BAND_TABLE = (
    (39, 9.0),
    (37, 8.5),
    (35, 8.0),
    (33, 7.5),
    (30, 7.0),
    (27, 6.5),
    (23, 6.0),
    (20, 5.5),
    (16, 5.0),
    (13, 4.5),
    (10, 4.0),
    (8, 3.5),
    (6, 3.0),
    (4, 2.5),
    (3, 2.0),
    (2, 1.5),
    (1, 1.0),
    (0, 0.0),
)


def _band(correct: int) -> float:
    """The estimate band for a raw score out of 40."""
    for floor, band in _BAND_TABLE:
        if correct >= floor:
            return band
    return 0.0


@scoring("ielts_band")
def score(result: RawResult, test: TestSpec) -> Score:
    """Estimate an IELTS-style band (not an official score).

    Each section's raw score is scaled to 40 questions (a short test counts as
    if it had 40), mapped to a band through our own estimate table, then the
    section bands are averaged and rounded to the nearest half band. The raw
    score is the marks of the section (one mark per correct question, minus
    the wrong penalty the core already applied).
    """
    section_bands: dict[str, float] = {}
    for section_id, spec in test.sections.items():
        section = result.sections.get(section_id)
        if section is None or spec.total <= 0:
            section_bands[section_id] = 0.0
            continue
        scaled = round(section.marks * 40 / spec.total)
        section_bands[section_id] = _band(scaled)

    if section_bands:
        average = sum(section_bands.values()) / len(section_bands)
        overall = math.floor(average * 2 + 0.5) / 2  # nearest half band
    else:
        overall = 0.0

    correct = sum(section.correct for section in result.sections.values())
    wrong = sum(section.wrong for section in result.sections.values())
    blank = sum(section.blank for section in result.sections.values())
    return Score(
        score=overall,
        score_type="band",
        sections=section_bands,
        correct=correct,
        wrong=wrong,
        blank=blank,
    )
