"""PKN STAN entrance test, coming soon on the id site."""

from __future__ import annotations

from cendekiara.core.plugins import ExamDef

EXAM = ExamDef(
    id="pkn-stan",
    category="seleksi-kedinasan",
    scoring="scale_200_800",
    layout="cbt",
    content_lang="id",
    features=("math",),
    status="coming_soon",
    sections={
        "tpa": (),
        "tbi": (),
    },
    sites=("id",),
)
