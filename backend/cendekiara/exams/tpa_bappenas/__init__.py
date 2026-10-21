"""TPA Bappenas (Tes Potensi Akademik), 200-800, the active exam."""

from __future__ import annotations

from cendekiara.core.plugins import ExamDef

EXAM = ExamDef(
    id="tpa-bappenas",
    category="seleksi-kedinasan",
    scoring="scale_200_800",
    layout="cbt",
    content_lang="id",
    features=("math",),
    status="active",
    sections={
        "verbal": ("sinonim", "antonim", "analogi", "pengelompokan-kata", "pemahaman-bacaan"),
        "kuantitatif": (
            "deret-angka",
            "aritmetika",
            "aljabar",
            "perbandingan-kuantitatif",
            "soal-cerita",
            "geometri",
        ),
        "penalaran": (
            "silogisme",
            "logika-proposisi",
            "logika-analitis",
            "deret-huruf",
            "pola-gambar",
            "spasial",
        ),
    },
    sites=("id",),
)
