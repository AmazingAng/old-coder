"""Scenario tests — each test name maps 1:1 to a spec.md scenario."""

import math
import sys
import threading
from typing import Any

import pytest
from conftest import FakeClock

from ratelimiter import RateLimiter


def test_requests_under_the_limit_are_allowed(clock: FakeClock) -> None:
    limiter = RateLimiter(limit=3, window_seconds=60, clock=clock)
    assert [limiter.allow("k") for _ in range(3)] == [True, True, True]


def test_request_over_the_limit_is_denied(clock: FakeClock) -> None:
    limiter = RateLimiter(limit=3, window_seconds=60, clock=clock)
    for _ in range(3):
        assert limiter.allow("k") is True
    clock.now = 59.0
    assert limiter.allow("k") is False


def test_denied_requests_do_not_consume_quota(clock: FakeClock) -> None:
    limiter = RateLimiter(limit=1, window_seconds=60, clock=clock)
    assert limiter.allow("k") is True
    clock.now = 10.0
    for _ in range(5):
        assert limiter.allow("k") is False
    clock.now = 61.0
    assert limiter.allow("k") is True


def test_window_slides_old_requests_expire_individually(clock: FakeClock) -> None:
    limiter = RateLimiter(limit=2, window_seconds=10, clock=clock)
    assert limiter.allow("k") is True  # t=0
    clock.now = 5.0
    assert limiter.allow("k") is True  # t=5
    clock.now = 10.1
    assert limiter.allow("k") is True  # t=0 left the window
    clock.now = 10.2
    assert limiter.allow("k") is False  # t=5 and t=10.1 still inside


def test_keys_are_isolated(clock: FakeClock) -> None:
    limiter = RateLimiter(limit=1, window_seconds=60, clock=clock)
    assert limiter.allow("a") is True
    assert limiter.allow("a") is False  # "a" exhausted
    assert limiter.allow("b") is True


@pytest.mark.parametrize(
    ("limit", "window", "bad_param"),
    [
        (0, 60, "limit"),
        (-1, 60, "limit"),
        (3, 0, "window_seconds"),
        (3, -5, "window_seconds"),
    ],
)
def test_invalid_construction_is_rejected(
    clock: FakeClock, limit: int, window: float, bad_param: str
) -> None:
    with pytest.raises(ValueError, match=bad_param):
        RateLimiter(limit=limit, window_seconds=window, clock=clock)


@pytest.mark.parametrize("window", [math.nan, math.inf, -math.inf])
def test_non_finite_window_is_rejected(clock: FakeClock, window: float) -> None:
    with pytest.raises(ValueError, match="window_seconds"):
        RateLimiter(limit=1, window_seconds=window, clock=clock)


def test_request_at_exact_window_boundary_is_still_limited(clock: FakeClock) -> None:
    limiter = RateLimiter(limit=1, window_seconds=60, clock=clock)
    assert limiter.allow("k") is True  # t=0
    clock.now = 60.0
    assert limiter.allow("k") is False  # age == window: still inside the window


def test_must_not_denials_store_nothing(clock: FakeClock) -> None:
    limiter = RateLimiter(limit=1, window_seconds=60, clock=clock)
    assert limiter.allow("k") is True
    snapshot = {key: list(hits) for key, hits in limiter._hits.items()}
    for _ in range(100):
        assert limiter.allow("k") is False
    assert {key: list(hits) for key, hits in limiter._hits.items()} == snapshot


def test_non_monotonic_clock_does_not_grant_extra_quota(clock: FakeClock) -> None:
    limiter = RateLimiter(limit=1, window_seconds=60, clock=clock)
    clock.now = 100.0
    assert limiter.allow("k") is True
    # The jump must exceed window_seconds: a smaller one leaves the hit inside
    # the window anyway, so it cannot distinguish an age of `now - hit` from
    # `abs(now - hit)` — the fail-open form. [REVISION 4]
    clock.now = 0.0  # backward by 100s, window is 60s
    assert limiter.allow("k") is False  # must fail closed


@pytest.mark.parametrize("limit", [math.nan, math.inf, -math.inf, 2.5, True])
def test_limit_must_be_a_finite_positive_integer(clock: FakeClock, limit: Any) -> None:
    with pytest.raises(ValueError, match="limit"):
        RateLimiter(limit=limit, window_seconds=60, clock=clock)


@pytest.mark.parametrize(
    ("key", "expected"),
    [(None, TypeError), (12345, TypeError), (b"bytes", TypeError), ("", ValueError)],
)
def test_key_must_be_a_non_empty_string(
    clock: FakeClock, key: Any, expected: type[Exception]
) -> None:
    limiter = RateLimiter(limit=1, window_seconds=60, clock=clock)
    with pytest.raises(expected, match="key"):
        limiter.allow(key)


def test_idle_keys_are_forgotten_key_map_is_bounded(clock: FakeClock) -> None:
    limiter = RateLimiter(limit=1, window_seconds=60, clock=clock)
    for i in range(1000):
        assert limiter.allow(f"one-shot-{i}") is True
    assert len(limiter._hits) == 1000
    clock.now = 121.0  # a full window has elapsed and none of them came back
    assert limiter.allow("someone-else") is True
    assert len(limiter._hits) == 1


def _allowed_in_one_race(limiter: RateLimiter, threads: int) -> int:
    """Fire `threads` simultaneous allow() calls; return how many won."""
    barrier = threading.Barrier(threads)
    results: list[bool] = []
    guard = threading.Lock()

    def worker() -> None:
        barrier.wait()
        got = limiter.allow("k")
        with guard:
            results.append(got)

    workers = [threading.Thread(target=worker) for _ in range(threads)]
    for w in workers:
        w.start()
    for w in workers:
        w.join()
    return sum(results)


def test_concurrent_callers_never_exceed_the_limit() -> None:
    rounds, threads = 60, 16
    previous_interval = sys.getswitchinterval()
    sys.setswitchinterval(1e-6)  # widen the preemption window
    try:
        worst = max(
            _allowed_in_one_race(
                RateLimiter(limit=1, window_seconds=60, clock=lambda: 0.0), threads
            )
            for _ in range(rounds)
        )
    finally:
        sys.setswitchinterval(previous_interval)
    assert worst == 1
