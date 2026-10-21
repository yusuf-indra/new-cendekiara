"""Sample data for the memory store: one JSON file per collection.

`load_seed()` is only used for `STORE=memory` (local dev and tests), never for
Firestore. It reads every `*.json` file in this directory and treats the file
name (without `.json`) as the collection name; the JSON object maps document
ids to documents (docs/02-data-model.md).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

Seed = dict[str, dict[str, dict[str, Any]]]


def load_seed() -> Seed:
    """Read the seed: collection -> doc id -> document, keyed by file name."""
    seed: Seed = {}
    for path in sorted(Path(__file__).parent.glob("*.json")):
        collection = path.stem
        seed[collection] = json.loads(path.read_text(encoding="utf-8"))
    return seed
