"""GMAT-style exam, coming soon on the global site."""

from __future__ import annotations

from cendekiara.core.plugins import ExamDef

EXAM = ExamDef(
    id="gmat",
    category="english",
    scoring="scale_200_800",  # GMAT total is also a 200-800 scale
    layout="cbt",
    content_lang="en",
    features=("math",),
    status="coming_soon",
    sections={
        "quantitative": (),
        "verbal": (),
        "integrated-reasoning": (),
        "analytical-writing": (),
    },
    sites=("global",),
)
