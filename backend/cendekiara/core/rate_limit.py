"""An in-memory rate limiter for the commands a student can hammer.

The limiter is per process, so on Cloud Run every instance has its own
counters; a shared limiter is a Phase 8 follow-up (docs/PROGRESS.md). The
clock is the core clock, so the tests can freeze it.
"""

from __future__ import annotations

from collections import defaultdict, deque
from threading import Lock

from cendekiara.core.clock import now

# How many calls a bucket may make in the window.
DEFAULT_LIMIT = 30
DEFAULT_WINDOW_SEC = 60


class RateLimiter:
    """A sliding-window limiter: one bucket per (key, name)."""

    def __init__(self, window_sec: int = DEFAULT_WINDOW_SEC) -> None:
        self._window = window_sec
        self._buckets: dict[tuple[str, str], deque[float]] = defaultdict(deque)
        self._lock = Lock()

    def allow(self, key: str, name: str, limit: int = DEFAULT_LIMIT) -> bool:
        """Is one more call allowed for this key? A limit of 0 allows everything."""
        if limit <= 0:
            return True
        current = now().timestamp()
        with self._lock:
            bucket = self._buckets[(key, name)]
            while bucket and current - bucket[0] > self._window:
                bucket.popleft()
            if len(bucket) >= limit:
                return False
            bucket.append(current)
            return True

    def reset(self) -> None:
        """Forget every bucket (the tests)."""
        with self._lock:
            self._buckets.clear()


limiter = RateLimiter()
