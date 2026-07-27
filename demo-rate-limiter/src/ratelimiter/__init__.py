"""Sliding-window rate limiter with an injectable clock."""

import math
from collections import deque
from collections.abc import Callable

__all__ = ["RateLimiter"]


class RateLimiter:
    """Allow at most `limit` requests per key within any sliding window.

    `clock` returns the current time in seconds; timestamps older than
    `window_seconds` fall out of the window individually. A backward-jumping
    clock fails closed: past hits never expire early.
    """

    def __init__(
        self, limit: int, window_seconds: float, clock: Callable[[], float]
    ) -> None:
        if limit <= 0:
            raise ValueError(f"limit must be positive, got {limit}")
        if not math.isfinite(window_seconds) or window_seconds <= 0:
            raise ValueError(
                f"window_seconds must be positive and finite, got {window_seconds}"
            )
        self._limit = limit
        self._window = window_seconds
        self._clock = clock
        self._hits: dict[str, deque[float]] = {}

    def allow(self, key: str) -> bool:
        """Record and allow this request, or deny it. Denials store nothing."""
        now = self._clock()
        hits = self._prune(key, now)
        if len(hits) >= self._limit:
            return False
        hits.append(now)
        self._hits[key] = hits
        return True

    def _prune(self, key: str, now: float) -> deque[float]:
        """Drop hits older than the window; forget keys with none left."""
        hits = self._hits.get(key, deque())
        while hits and now - hits[0] > self._window:
            hits.popleft()
        if not hits:
            self._hits.pop(key, None)
        return hits
