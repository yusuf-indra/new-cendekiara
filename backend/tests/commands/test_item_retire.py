"""item.retire: retire a single item, not_found, admin-only, allow_jobs=True."""

from __future__ import annotations

import pytest

from cendekiara.core import registry
from cendekiara.core.context import Context
from cendekiara.core.errors import AppError
from tests.item_helpers import make_item


def test_item_retire_marks_the_item_retired(admin_ctx: Context) -> None:
    registry.execute("item.create", {"item": make_item()}, admin_ctx)
    out = registry.execute("item.retire", {"item_id": "tpa-test-1"}, admin_ctx)
    assert out.model_dump() == {"id": "tpa-test-1", "status": "retired"}
    assert admin_ctx.store.get("items", "tpa-test-1")["status"] == "retired"  # type: ignore[index]


def test_item_retire_of_a_missing_item_is_not_found(admin_ctx: Context) -> None:
    with pytest.raises(AppError) as err:
        registry.execute("item.retire", {"item_id": "nope"}, admin_ctx)
    assert err.value.code == "not_found"


def test_item_retire_needs_admin(ctx: Context) -> None:
    with pytest.raises(AppError) as err:
        registry.execute("item.retire", {"item_id": "x"}, ctx)
    assert err.value.code == "admin_only"


def test_item_retire_allows_jobs() -> None:
    info = registry.get("item.retire")
    assert info.admin_only is True
    assert info.allow_jobs is True
