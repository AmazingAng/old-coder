# Evidence Report — Sliding-Window Rate Limiter (Tier 3)

- Spec approval: **not obtained (autonomous run)** — confidence claim is
  correspondingly reduced; `spec.md` is the artifact to review after the fact.
- Source state: git commit `46417c8`; sha256 tree hash `d1388f71a8a8c6f3`
  (over `src tests tools examples pyproject.toml requirements-dev.txt
  spec.md`, recompute with `find <those paths> -type f -not -path
  "*__pycache__*" | sort | xargs shasum -a 256 | shasum -a 256`).
- Toolchain: pinned in `requirements-dev.txt` (local run: Python 3.14.3;
  CI runs the same gauntlet on 3.12 via `.github/workflows/gauntlet.yml`).
- Entry point: `./tools/gauntlet.sh` reruns every layer below.

All numbers are from one final fresh run of the entry point, executed
2026-07-27 after the last code edit.

## Spec → Test mapping

Status legend: pass / fail / unverified / n-a.

| Scenario | Test | Status |
|---|---|---|
| requests under the limit are allowed | test_ratelimiter.py::test_requests_under_the_limit_are_allowed | pass |
| request over the limit is denied | test_ratelimiter.py::test_request_over_the_limit_is_denied | pass |
| denied requests do not consume quota | test_ratelimiter.py::test_denied_requests_do_not_consume_quota | pass |
| window slides — old requests expire individually | test_ratelimiter.py::test_window_slides_old_requests_expire_individually | pass |
| keys are isolated | test_ratelimiter.py::test_keys_are_isolated | pass |
| invalid construction is rejected | test_ratelimiter.py::test_invalid_construction_is_rejected (4 params) | pass |
| non-finite window is rejected (spec revision) | test_ratelimiter.py::test_non_finite_window_is_rejected (3 params) | pass |
| non-monotonic clock does not grant extra quota | test_ratelimiter.py::test_non_monotonic_clock_does_not_grant_extra_quota | pass |
| request at the exact window boundary is still limited (spec revision 2) | test_ratelimiter.py::test_request_at_exact_window_boundary_is_still_limited + mutant M2 | pass |
| Invariant P1 (window count ≤ limit) | test_properties.py::test_p1_allowed_count_within_any_window_never_exceeds_limit | pass |
| Invariant P2 (key independence) | test_properties.py::test_p2_other_keys_traffic_never_changes_one_keys_outcomes | pass |
| Must NOT: denials store nothing (no memory growth) | test_ratelimiter.py::test_must_not_denials_store_nothing + mutant M8 | pass |
| Must NOT: no real sleep/wall-clock in tests | layer: `grep -rn "time\." tests/` → no matches (FakeClock only) | pass |

## Gauntlet (final fresh run: `./tools/gauntlet.sh`)

| Layer | Command | Result |
|---|---|---|
| Tests | `pytest -q --cov=ratelimiter` | 17 passed, 0 failed |
| Types | `mypy src tests examples tools` (strict) | 0 errors in 6 files |
| Lint + format | `ruff check . && ruff format --check .` | 0 warnings, 8 files formatted |
| Changed-line coverage | `pytest --cov … --cov-report=term-missing` | 29/29 statements, 10/10 branches (100%; entire module is new, so changed lines = all lines) |
| Mutation | `python tools/mutants.py` (manual, scripted; only pytest exit 1 counts as a kill — error exits are flagged, never counted) | 8/8 killed |
| Property-based | hypothesis, 2 properties | 100 examples each, 0 falsified |
| Real execution | `python examples/demo.py` (real `time.monotonic`) | burst of 5 → `[True, True, True, False, False]`; other key unaffected; allowed again after window |
| Supply chain | `pip-audit -r requirements-dev.txt` | no known vulnerabilities; runtime dependencies: **none** (stdlib only), dev toolchain pinned |
| Suite health | pytest-randomly (order shuffled every run, e.g. seed 2606823942) | 17 passed in randomized order |

## Skipped layers

- Tool-based mutation (mutmut): unverified compatibility with Python 3.14;
  replaced with the scripted manual procedure (`tools/mutants.py`, 8 mutants:
  comparison flips, boundary off-by-ones, dropped statements, fail-open
  inversion, wrong-end pruning, dropped validation, denial-side write).

## Honest notes

- **Spec approval was never obtained**: the demo ran autonomously, so the
  spec/tests/implementation/evidence share one author and the
  correlation-breaking human review has not happened. Treat `spec.md` as the
  review surface.
- Three scenario tests passed immediately when written (**keys are isolated**,
  **non-monotonic clock**, **Must NOT: denials store nothing**): the per-key
  deque design provides these inherently. Each was proven non-vacuous by a
  targeted mutant run (M5/M6/M8 respectively — M8 was run against the new test
  alone and killed).
- **Spec revision during the task**: the Tier 3 adversarial pass found that
  `window_seconds=NaN` passed the original `<= 0` validation; the spec was
  revised visibly, a RED test watched failing, then the finiteness check
  implemented (killed as M7).
- **Layer attribution** (historic, before M7/M8 existed): mutants vs the
  property suite alone gave 3/5 killed — M2 (expiry boundary) and M6
  (wrong-end pruning) survived. The headline kill score is carried by the
  scenario tests; P1 is one-sided ("never exceeds limit") and cannot catch
  fail-closed bugs. A lower-bound property remains a known improvement.
- **Flaky kill found on rerun** (2026-07-27): M2's kill turned out to depend
  on hypothesis randomly hitting the exact `age == window` boundary — a rerun
  reported it SURVIVED. Fixed properly: spec revision 2 added the boundary
  behavior, a deterministic test was written and proven non-vacuous against
  M2 alone. Property-based kills are stochastic; deterministic behaviors
  deserve deterministic tests.
- **Git history note**: the demo originally ran without git (restores were
  verified by suite rerun + tree hash). The repo is now under git; source
  state above cites the commit.
- Remaining known limits (out of spec scope): not thread-safe (no locking); a
  NaN-returning *clock* fails closed but is not rejected.
