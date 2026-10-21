"""The clock is UTC and can be frozen."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from cendekiara.core import clock

FIXED = datetime(2026, 10, 21, 9, 30, tzinfo=UTC)


def test_now_is_utc() -> None:
    clock.unfreeze()
    assert clock.now().tzinfo is UTC


def test_freeze_stops_the_clock() -> None:
    clock.freeze(FIXED)
    assert clock.now() == FIXED
    assert clock.now_iso() == FIXED.isoformat()


def test_unfreeze_restores_the_wall_clock() -> None:
    past = datetime(2020, 1, 1, tzinfo=UTC)
    clock.freeze(past)
    clock.unfreeze()
    assert clock.now() > past


def test_freeze_needs_an_aware_datetime() -> None:
    with pytest.raises(ValueError):
        clock.freeze(datetime(2026, 10, 21, 9, 30))
