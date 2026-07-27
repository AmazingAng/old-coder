"""Scenario tests — each test name maps 1:1 to a spec.md scenario."""

import math

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
    clock.now = 50.0  # clock jumps backward
    assert limiter.allow("k") is False  # must fail closed
