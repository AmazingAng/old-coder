"""Sliding-window rate limiter with an injectable clock."""

import math
import threading
from collections import deque
from collections.abc import Callable

__all__ = ["RateLimiter"]


def _validate(limit: int, window_seconds: float) -> None:
    """Reject any configuration that would silently never or always allow.

    Extracted from __init__ so that adding the window_seconds type guard did
    not push the constructor to the top of the complexity budget. `bool` is
    excluded explicitly: it is a subclass of int, so True would otherwise be
    accepted as a limit of 1 and a window of 1.0 second.
    """
    if isinstance(limit, bool) or not isinstance(limit, int):
        raise ValueError(f"limit must be an integer, got {limit!r}")
    if limit <= 0:
        raise ValueError(f"limit must be positive, got {limit}")
    if isinstance(window_seconds, bool) or not isinstance(window_seconds, int | float):
        raise ValueError(f"window_seconds must be a number, got {window_seconds!r}")
    if not math.isfinite(window_seconds) or window_seconds <= 0:
        raise ValueError(
            f"window_seconds must be positive and finite, got {window_seconds}"
        )


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
        _validate(limit, window_seconds)
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
        # The clock read belongs inside the lock. Read outside it, two callers
        # can commit in the opposite order from which they read the clock, and
        # the deque that _prune and _sweep both assume is ascending stops being
        # so; _sweep then reads a stale newest-hit and forgets a key that still
        # has a live hit, resetting that caller's quota. Cost: `clock` must not
        # call back into this limiter (see the clock contract).
        with self._lock:
            now = self._clock()
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
        """Drop hits older than the window. Forgetting keys is _sweep's job."""
        hits = self._hits.get(key, deque())
        while hits and now - hits[0] > self._window:
            hits.popleft()
        return hits
