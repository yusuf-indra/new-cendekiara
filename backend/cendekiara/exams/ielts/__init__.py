"""IELTS-style exam (layout split, band scoring)."""

from __future__ import annotations

from cendekiara.core.plugins import ExamDef

EXAM = ExamDef(
    id="ielts",
    category="english",
    scoring="ielts_band",
    layout="split",
    content_lang="en",
    status="active",
    sections={
        "listening": (),
        "reading": (),
        "writing": (),
        "speaking": (),
    },
    sites=("id", "global"),
)
