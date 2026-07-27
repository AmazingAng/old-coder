"""Property-based tests for the spec invariants P1 and P2."""

from conftest import FakeClock
from hypothesis import given
from hypothesis import strategies as st

from ratelimiter import RateLimiter

requests = st.lists(
    st.tuples(
        st.floats(min_value=0, max_value=1000, allow_nan=False, allow_infinity=False),
        st.sampled_from("abc"),
    ),
    max_size=60,
)
limits = st.integers(min_value=1, max_value=5)
windows = st.floats(min_value=0.1, max_value=100, allow_nan=False)


def run(
    limiter: RateLimiter, clock: FakeClock, steps: list[tuple[float, str]]
) -> list[tuple[float, str, bool]]:
    outcomes = []
    for t, key in steps:
        clock.now = t
        outcomes.append((t, key, limiter.allow(key)))
    return outcomes


@given(steps=requests, limit=limits, window=windows)
def test_p1_allowed_count_within_any_window_never_exceeds_limit(
    steps: list[tuple[float, str]], limit: int, window: float
) -> None:
    steps.sort(key=lambda s: s[0])  # monotone clock
    clock = FakeClock()
    outcomes = run(RateLimiter(limit, window, clock), clock, steps)
    for t, key, allowed in outcomes:
        if not allowed:
            continue
        in_window = sum(
            1 for t2, k2, ok in outcomes if ok and k2 == key and 0 <= t - t2 <= window
        )
        assert in_window <= limit


@given(steps=requests, limit=limits, window=windows)
def test_p2_other_keys_traffic_never_changes_one_keys_outcomes(
    steps: list[tuple[float, str]], limit: int, window: float
) -> None:
    steps.sort(key=lambda s: s[0])
    clock_full = FakeClock()
    full = run(RateLimiter(limit, window, clock_full), clock_full, steps)
    only_a = [s for s in steps if s[1] == "a"]
    clock_solo = FakeClock()
    solo = run(RateLimiter(limit, window, clock_solo), clock_solo, only_a)
    assert [o for o in full if o[1] == "a"] == solo
