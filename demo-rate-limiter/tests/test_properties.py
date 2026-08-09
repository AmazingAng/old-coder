"""Property-based tests for the spec invariants P1 and P2."""

from conftest import FakeClock
from hypothesis import given
from hypothesis import strategies as st

from ratelimiter import RateLimiter

timestamps = st.floats(
    min_value=0, max_value=1000, allow_nan=False, allow_infinity=False
)
# [REVISION 4] Keys were `st.sampled_from("abc")`, so the whole suite ever saw
# three distinct keys and an implementation hardcoded to them scored 100%
# coverage and 8/8 mutants. A small alphabet keeps collisions frequent (which
# is what makes P1 bite) while ranging far outside any hardcoded set.
# Widening this too far blunts the layer: with 258 possible keys and limits up
# to 20, hypothesis almost never drives one key to its limit, so the deny
# branch goes unexercised and the fail-open mutant M5 survives the property
# suite. 12 keys keeps collisions frequent while still ranging outside any
# hardcoded key set. Measured by the layer-attribution run, not guessed.
keys = st.text(alphabet="abc", min_size=1, max_size=2)
requests = st.lists(st.tuples(timestamps, keys), max_size=60)
# P2 needs the target key to recur, so it keeps a small pool — but the pool is
# no longer three single characters. The widening above was applied to P1 only
# in the first pass, directly under the comment explaining it; P2 was left
# behind and killed none of M1/M5/M12 in attribution.
isolation_keys = st.sampled_from(["a", "ab", "Ab", "b", "bc", "c", "c "])
isolation_requests = st.lists(st.tuples(timestamps, isolation_keys), max_size=60)
limits = st.integers(min_value=1, max_value=5)
# Mostly ordinary windows, sometimes far outside the tested range, so an
# implementation that special-cases large windows cannot hide.
windows = st.one_of(
    st.floats(min_value=0.1, max_value=100, allow_nan=False),
    st.floats(min_value=1001, max_value=5000, allow_nan=False),
)


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


@given(steps=isolation_requests, limit=limits, window=windows)
def test_p2_other_keys_traffic_never_changes_one_keys_outcomes(
    steps: list[tuple[float, str]], limit: int, window: float
) -> None:
    if not steps:
        return
    steps.sort(key=lambda s: s[0])
    # Take the target from the data rather than hardcoding "a": with a wider
    # key pool a fixed target is often absent, and the property then holds
    # vacuously over two empty lists.
    target = steps[0][1]
    clock_full = FakeClock()
    full = run(RateLimiter(limit, window, clock_full), clock_full, steps)
    only_target = [s for s in steps if s[1] == target]
    clock_solo = FakeClock()
    solo = run(RateLimiter(limit, window, clock_solo), clock_solo, only_target)
    assert [o for o in full if o[1] == target] == solo
