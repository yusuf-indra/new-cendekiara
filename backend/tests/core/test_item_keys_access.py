"""No command outside item.* and bank.export may touch the item_keys collection."""

from __future__ import annotations

from pathlib import Path

import cendekiara


def test_only_item_commands_and_bank_export_read_item_keys() -> None:
    commands_dir = Path(cendekiara.__file__).parent / "commands"
    offenders: list[str] = []
    for path in commands_dir.glob("*.py"):
        if "item_keys" not in path.read_text(encoding="utf-8"):
            continue
        name = path.stem
        if not (name.startswith("item_") or name == "bank_export"):
            offenders.append(name)
    assert offenders == []
