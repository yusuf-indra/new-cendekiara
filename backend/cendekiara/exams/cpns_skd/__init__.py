"""CPNS SKD (Seleksi Kompetensi Dasar), coming soon on the id site."""

from __future__ import annotations

from cendekiara.core.plugins import ExamDef

EXAM = ExamDef(
    id="cpns-skd",
    category="seleksi-kedinasan",
    scoring="cpns_skd",  # the method arrives in a later phase (docs/04-exams.md)
    layout="cbt",
    content_lang="id",
    features=("math",),
    status="coming_soon",
    sections={
        "twk": (),
        "tiu": (),
        "tkp": (),
    },
    sites=("id",),
)
