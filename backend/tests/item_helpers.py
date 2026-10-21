"""Builders for valid TPA items and keys, shared across command tests."""

from __future__ import annotations

from typing import Any


def make_item(item_id: str = "tpa-test-1", **overrides: Any) -> dict[str, Any]:
    """A minimal, valid TPA quantitative choice item."""
    item: dict[str, Any] = {
        "id": item_id,
        "exam": "tpa-bappenas",
        "section": "kuantitatif",
        "tags": ["deret"],
        "difficulty": 2,
        "targetTimeSec": 45,
        "status": "active",
        "usage": {"exam": True, "practice": True, "study": True},
        "sites": ["id"],
        "stimulus": None,
        "groups": [
            {
                "id": "g1",
                "type": "choice",
                "topic": "deret-angka",
                "instructions": "Pilih jawaban yang tepat.",
                "options": [
                    {"id": "A", "text": "24"},
                    {"id": "B", "text": "26"},
                    {"id": "C", "text": "28"},
                    {"id": "D", "text": "30"},
                ],
                "questions": [{"id": "q1", "prompt": "2, 5, 10, 17, ..."}],
            }
        ],
    }
    item.update(overrides)
    return item


def make_key(item_id: str = "tpa-test-1", answer: str = "B") -> dict[str, Any]:
    """A key matching `make_item`."""
    return {
        "id": item_id,
        "answers": {"q1": [answer]},
        "explanations": {"q1": "Penjelasan singkat."},
        "transcript": None,
        "aiCheck": None,
    }
