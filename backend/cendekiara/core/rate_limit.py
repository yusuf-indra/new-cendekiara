"""In-memory rate limiter (per Cloud Run instance)."""

from __future__ import annotations

import time
from collections import defaultdict, deque

_LOCKS: dict[tuple[str, str], deque[float]] = defaultdict(deque)


def check_rate_limit(key: str, bucket: str, limit: int, window_sec: int = 60) -> bool:
    if limit <= 0:
        return True
    now = time.monotonic()
    k = (key, bucket)
    q = _LOCKS[k]
    while q and now - q[0] > window_sec:
        q.popleft()
    if len(q) >= limit:
        return False
    q.append(now)
    return True


def reset() -> None:
    _LOCKS.clear()
