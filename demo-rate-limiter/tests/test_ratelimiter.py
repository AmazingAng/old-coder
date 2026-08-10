"""Scenario tests. Most map 1:1 to a spec.md scenario; the rest map to a
Must NOT clause or to a failure-model row (24 tests, 22 scenarios)."""

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


@pytest.mark.parametrize("window", [True, "60", None])
def test_window_seconds_must_be_a_number(clock: FakeClock, window: Any) -> None:
    # bool is an int subclass, so window_seconds=True would build a 1.0-second
    # window; "60" would raise a bare TypeError instead of naming the parameter.
    with pytest.raises(ValueError, match="window_seconds"):
        RateLimiter(limit=1, window_seconds=window, clock=clock)


def test_keys_are_compared_as_exact_strings(clock: FakeClock) -> None:
    # Every key elsewhere in the suite is lowercase and unpadded, so key
    # normalisation is otherwise structurally invisible. Case, padding and a
    # whitespace-only key are all pinned: the contract is "non-empty str".
    limiter = RateLimiter(limit=1, window_seconds=60, clock=clock)
    assert limiter.allow("Alice") is True
    assert limiter.allow("alice") is True  # a different caller, not the same one
    assert limiter.allow("alice ") is True  # and so is this one
    assert limiter.allow(" ") is True  # non-empty, therefore a caller
    assert limiter.allow("Alice") is False


def test_sweep_keeps_a_key_whose_newest_hit_is_exactly_window_old(
    clock: FakeClock,
) -> None:
    # _sweep re-implements _prune's age comparison, so it needs its own
    # boundary test: a >= there forgets a key that still has a live hit.
    limiter = RateLimiter(limit=1, window_seconds=60, clock=clock)
    assert limiter.allow("other") is True  # t=0, arms the sweep clock
    clock.now = 1.0
    assert limiter.allow("k") is True
    clock.now = 61.0  # sweep fires; k's only hit is exactly 60s old
    assert limiter.allow("k") is False


def test_a_key_is_dropped_by_the_first_sweep_after_one_idle_window(
    clock: FakeClock,
) -> None:
    # Pins the idle threshold's MAGNITUDE, not just its boundary: every other
    # memory test asserts deletion only at age >= 2W, so any threshold in
    # (W, 2W) satisfies them all.
    limiter = RateLimiter(limit=5, window_seconds=60, clock=clock)
    assert limiter.allow("armer") is True  # t=0, arms the sweep clock
    assert limiter.allow("idle") is True  # t=0
    clock.now = 61.0  # first sweep after t=0; idle is 61s old, one window+
    assert limiter.allow("probe") is True
    assert "idle" not in limiter._hits, "idle threshold is larger than a window"


def test_the_memory_bound_is_two_windows_not_one(clock: FakeClock) -> None:
    # The throttle means residency reaches 2W. Pins both sides, so a bound of
    # one window and a bound of three are each rejected.
    limiter = RateLimiter(limit=5, window_seconds=60, clock=clock)
    assert limiter.allow("armer") is True  # t=0, arms the sweep clock
    clock.now = 1.0
    assert limiter.allow("idle") is True  # last hit at t=1
    clock.now = 60.9  # sweep fires: drops armer, keeps idle
    assert limiter.allow("probe") is True
    clock.now = 100.0  # idle for 99s — already longer than one window
    assert limiter.allow("probe") is True
    assert "idle" in limiter._hits, "one window is not the real bound"
    clock.now = 121.0  # next sweep is now due
    assert limiter.allow("probe") is True
    assert "idle" not in limiter._hits, "two windows must be the bound"


def test_the_first_call_always_sweeps(clock: FakeClock) -> None:
    # The -inf sentinel exists so the first call is never throttled. Every
    # other clock in the suite starts at 0.0 or past a full window, so a
    # sentinel of 0.0 would have been indistinguishable.
    limiter = RateLimiter(limit=1, window_seconds=60, clock=clock)
    clock.now = 30.0
    assert limiter.allow("k") is True
    assert limiter._last_sweep == 30.0, "first call did not sweep"


def test_memory_is_not_reclaimed_while_traffic_is_silent(clock: FakeClock) -> None:
    # The sweep runs only inside allow(), so the bound is "keys seen in the two
    # windows preceding the most recent request" — not two windows of wall
    # time. Every other memory test probes after issuing a request, which is
    # exactly the case the lazy sweep handles.
    limiter = RateLimiter(limit=1, window_seconds=60, clock=clock)
    for i in range(50):
        assert limiter.allow(f"k{i}") is True
    clock.now = 10_000_000.0  # ~166,000 windows pass with no traffic
    assert len(limiter._hits) == 50, "nothing is reclaimed without a request"
    assert limiter.allow("probe") is True
    assert len(limiter._hits) == 1


def test_backward_clock_skew_does_not_suspend_the_sweep(clock: FakeClock) -> None:
    # A one-sided throttle leaves `now` permanently below the last sweep time
    # after a backward jump, suspending reclamation entirely. Quota fails
    # closed under skew; memory has to be checked separately.
    limiter = RateLimiter(limit=1, window_seconds=60, clock=clock)
    clock.now = 1_000_000.0
    assert limiter.allow("arm") is True
    clock.now = 0.0  # clock jumps backward
    for i in range(200):
        clock.now = i * 2.0
        limiter.allow(f"key-{i}")
    assert len(limiter._hits) < 100, f"sweep suspended: {len(limiter._hits)} keys held"


def test_the_sweep_is_throttled_to_once_per_window(clock: FakeClock) -> None:
    # The throttle carries the accepted-residual-risk argument, so it needs a
    # catcher of its own: without one, the sweep degrades to an O(keys) scan
    # on every request invisibly.
    limiter = RateLimiter(limit=5, window_seconds=60, clock=clock)
    assert limiter.allow("k") is True
    assert limiter._last_sweep == 0.0
    clock.now = 30.0
    assert limiter.allow("k") is True
    assert limiter._last_sweep == 0.0, "swept again inside the same window"
    clock.now = 60.0  # delta is exactly one window: still throttled
    assert limiter.allow("k") is True
    assert limiter._last_sweep == 0.0, "swept at the boundary; <= means <="
    clock.now = 61.0
    assert limiter.allow("k") is True
    assert limiter._last_sweep == 61.0, "did not sweep after a full window"


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


def test_allow_is_atomic_a_second_caller_cannot_interleave(clock: FakeClock) -> None:
    """Deterministic counterpart to the stress test below: fault injection.

    The stress test is a statistical detector (measured per-round detection
    rate 5.9%), so it can only bound the miss probability, never eliminate it.
    Here the interleaving is constructed: a one-shot gate holds the first
    caller inside the critical section. Holding the lock, the second caller
    blocks before reaching the gate; without it, the second caller walks in,
    sees state the first has not written yet, and is allowed.
    """
    limiter = RateLimiter(limit=1, window_seconds=60, clock=clock)
    inside, release = threading.Event(), threading.Event()
    original_prune = limiter._prune
    gated: list[int] = []

    def prune_once_gated(key: str, now: float) -> Any:
        if not gated:
            gated.append(1)
            inside.set()
            release.wait(timeout=5)
        return original_prune(key, now)

    limiter._prune = prune_once_gated  # type: ignore[method-assign]
    results: list[bool] = []
    first = threading.Thread(target=lambda: results.append(limiter.allow("k")))
    first.start()
    assert inside.wait(timeout=5), "first caller never entered the critical section"
    second = threading.Thread(target=lambda: results.append(limiter.allow("k")))
    second.start()
    second.join(timeout=0.2)
    assert second.is_alive(), "second caller entered while the first held the lock"
    release.set()
    first.join(timeout=5)
    second.join(timeout=5)
    assert sorted(results) == [False, True]


def test_clock_is_read_inside_the_critical_section() -> None:
    """The lock must cover the clock read, not just the check-and-append.

    Both other concurrency tests hold time constant, so they cannot see this:
    with one clock value no ordering between threads is observable. If the
    read happens outside the lock, two callers can commit in the opposite
    order from which they read the clock, leaving the deque unsorted — and
    _sweep then judges the key by a stale newest-hit and deletes a key that
    still has a live hit, resetting that caller's quota. Fail-open.
    """
    times = iter([99.0, 100.0])
    first_read, second_done = threading.Event(), threading.Event()
    gated: list[int] = []

    def gated_clock() -> float:
        value = next(times)
        if not gated:
            gated.append(1)
            first_read.set()
            # Read inside the lock, the second caller is blocked and this
            # cannot be satisfied, so it times out and the order stays
            # correct. Read outside, the second caller finishes and inverts.
            second_done.wait(timeout=0.3)
        return value

    limiter = RateLimiter(limit=5, window_seconds=60, clock=gated_clock)
    first = threading.Thread(target=lambda: limiter.allow("k"))
    first.start()
    assert first_read.wait(timeout=5), "first caller never read the clock"

    def second_caller() -> None:
        limiter.allow("k")
        second_done.set()

    second = threading.Thread(target=second_caller)
    second.start()
    first.join(timeout=5)
    second.join(timeout=5)
    hits = list(limiter._hits["k"])
    # Both assertions matter: a one-element list is trivially sorted, so a
    # second caller that died would satisfy the ordering check vacuously.
    assert len(hits) == 2, f"a caller never committed: {hits}"
    assert hits == sorted(hits), f"commits inverted, deque unsorted: {hits}"


def test_concurrent_callers_never_exceed_the_limit() -> None:
    # 400 rounds at a measured per-round detection rate of 5.9% puts the miss
    # probability near 3e-11; at the original 60 rounds it was 2.7e-2, and the
    # mutant that removes the lock was observed surviving 1 run in 50.
    rounds, threads = 400, 16
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
