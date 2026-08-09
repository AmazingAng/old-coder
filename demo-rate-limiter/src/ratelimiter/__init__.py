"""Sliding-window rate limiter with an injectable clock."""

import math
import threading
from collections import deque
from collections.abc import Callable

__all__ = ["RateLimiter"]


class RateLimiter:
    """Allow at most `limit` requests per key within any sliding window.

    `clock` returns the current time in seconds and MUST be monotonic
    (`time.monotonic`); timestamps older than `window_seconds` fall out of the
    window individually. A backward-jumping clock fails closed: past hits never
    expire early. A forward jump expires every hit at once — that is a caller
    obligation, not a defect (see the clock contract in spec.md).

    Safe to call from multiple threads. Memory is bounded by the number of
    distinct keys seen within one window: keys idle for a full window are
    dropped by a sweep that runs at most once per window.
    """

    def __init__(
        self, limit: int, window_seconds: float, clock: Callable[[], float]
    ) -> None:
        if isinstance(limit, bool) or not isinstance(limit, int):
            raise ValueError(f"limit must be an integer, got {limit!r}")
        if limit <= 0:
            raise ValueError(f"limit must be positive, got {limit}")
        if not math.isfinite(window_seconds) or window_seconds <= 0:
            raise ValueError(
                f"window_seconds must be positive and finite, got {window_seconds}"
            )
        self._limit = limit
        self._window = window_seconds
        self._clock = clock
        self._lock = threading.Lock()
        self._hits: dict[str, deque[float]] = {}
        self._last_sweep = -math.inf

    def allow(self, key: str) -> bool:
        """Record and allow this request, or deny it. Denials store nothing."""
        if not isinstance(key, str):
            raise TypeError(f"key must be a str, got {type(key).__name__}")
        if not key:
            raise ValueError("key must not be empty")
        now = self._clock()
        with self._lock:
            self._sweep(now)
            hits = self._prune(key, now)
            if len(hits) >= self._limit:
                return False
            hits.append(now)
            self._hits[key] = hits
            return True

    def _sweep(self, now: float) -> None:
        """Forget keys idle for a full window. Runs at most once per window."""
        if now - self._last_sweep <= self._window:
            return
        self._last_sweep = now
        idle = [k for k, hits in self._hits.items() if now - hits[-1] > self._window]
        for key in idle:
            del self._hits[key]

    def _prune(self, key: str, now: float) -> deque[float]:
        """Drop hits older than the window; forget keys with none left."""
        hits = self._hits.get(key, deque())
        while hits and now - hits[0] > self._window:
            hits.popleft()
        if not hits:
            self._hits.pop(key, None)
        return hits
