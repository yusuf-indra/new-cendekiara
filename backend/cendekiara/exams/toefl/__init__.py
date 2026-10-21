"""TOEFL-style exam, coming soon on the global site."""

from __future__ import annotations

from cendekiara.core.plugins import ExamDef

EXAM = ExamDef(
    id="toefl",
    category="english",
    scoring="toefl",  # the method arrives in a later phase (docs/04-exams.md)
    layout="split",
    content_lang="en",
    status="coming_soon",
    sections={
        "reading": (),
        "listening": (),
        "speaking": (),
        "writing": (),
    },
    sites=("global",),
)
