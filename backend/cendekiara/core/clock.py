"""The clock. Commands never read the wall clock directly, so tests can freeze it."""

from __future__ import annotations

from datetime import UTC, datetime

_frozen: datetime | None = None


def now() -> datetime:
    """The current time in UTC (frozen while the clock is frozen)."""
    if _frozen is not None:
        return _frozen
    return datetime.now(UTC)


def now_iso() -> str:
    """The current time in UTC as an ISO-8601 string."""
    return now().isoformat()


def freeze(at: datetime) -> None:
    """Freeze the clock at `at` (timezone-aware, converted to UTC)."""
    global _frozen
    if at.tzinfo is None:
        raise ValueError("freeze() needs a timezone-aware datetime")
    _frozen = at.astimezone(UTC)


def unfreeze() -> None:
    """Let the clock run again."""
    global _frozen
    _frozen = None
