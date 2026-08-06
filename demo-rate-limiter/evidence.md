# Evidence Report — Sliding-Window Rate Limiter (Tier 3)

- Spec approval: **not obtained (autonomous run)** — confidence claim is
  correspondingly reduced; `spec.md` is the artifact to review after the fact.
- Source state: git commit `a0f54a1`; sha256 tree hash `a6b9851f5af585de` —
  reproduce both with `./tools/source_state.sh` (works from any directory).
- Toolchain: pinned in `requirements-dev.txt` (local run: Python 3.14.3;
  CI runs the same gauntlet on 3.12 via `.github/workflows/gauntlet.yml`).
- Entry point: `./tools/gauntlet.sh` reruns every layer below.

All numbers are from one final fresh run of the entry point, executed
2026-08-06 after the last code edit.

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
| Must NOT: no real sleep/wall-clock in tests | layer: must-not scan in `tools/gauntlet.sh` (`time\.` over tests/) → no matches (FakeClock only) | pass |

## Gauntlet (final fresh run: `./tools/gauntlet.sh`)

| Layer | Command | Result |
|---|---|---|
| Tests | `pytest -q --cov=ratelimiter` | 17 passed, 0 failed |
| Types | `mypy src tests examples tools` (strict) | 0 errors in 6 files |
| Lint + format + complexity | `ruff check . && ruff format --check .` (includes mccabe complexity budget ≤ 8) | 0 warnings, 8 files formatted |
| Changed-line coverage | `pytest --cov … --cov-report=term-missing` | 29/29 statements, 10/10 branches (100%; entire module is new, so changed lines = all lines) |
| Mutation | `python tools/mutants.py` (manual, scripted; only pytest exit 1 counts as a kill — error exits are flagged, never counted) | 8/8 killed |
| Property-based | hypothesis, 2 properties | 100 examples each, 0 falsified |
| Real execution | `python examples/demo.py` (real `time.monotonic`) | burst of 5 → `[True, True, True, False, False]`; other key unaffected; allowed again after window |
| Supply chain | `pip-audit -r requirements-dev.txt` | no known vulnerabilities; runtime dependencies: **none** (stdlib only), dev toolchain pinned & justified in spec setup plan |
| Secret scan | must-not scan in `tools/gauntlet.sh` (api key / secret / password / token / private key over src, tests, tools, examples) | clean, no matches |
| License check | — | n-a: zero runtime dependencies, nothing redistributed beyond this repo's own MIT code; dev tools are not shipped |
| Suite health | pytest-randomly (order shuffled every run; seed printed in non-quiet runs) | 17 passed in randomized order |

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
- **Layer attribution** (fresh, 2026-07-27, all 8 mutants): mutants vs the
  property suite alone give 3/8 killed (M1, M3, M5). Survivors and why:
  M4/M7 (validation — properties never construct invalid limiters), M2
  (exact boundary — stochastic inputs rarely hit it), M6/M8 (fail-closed
  direction — P1 is one-sided, "never exceeds limit" cannot catch
  under-allowing or hidden writes). The headline 8/8 is carried by the
  scenario tests; a lower-bound property remains a known improvement.
- **Flaky kill found on rerun** (2026-07-27): M2's kill turned out to depend
  on hypothesis randomly hitting the exact `age == window` boundary — a rerun
  reported it SURVIVED. Fixed properly: spec revision 2 added the boundary
  behavior, a deterministic test was written and proven non-vacuous against
  M2 alone. Property-based kills are stochastic; deterministic behaviors
  deserve deterministic tests.
- **Checker negative controls** (2026-08-06, prompted by a community issue on
  fail-open checkers): the two must-not greps were folded into
  `tools/gauntlet.sh` with explicit exit-code handling (grep rc 1 = pass,
  rc 0 = forbidden pattern found, rc ≥ 2 = broken check — both fail). Each
  failure branch was proven able to fire with one-off controls: a planted
  `time.sleep` fixture (failed as required), a chmod-000 unreadable file
  (failed closed), a nonexistent scan path (failed closed); fixtures removed
  after. During the fold-in the secret scan caught its own pattern literal in
  the script — a true positive, resolved by bracketing letters in the pattern
  (`s[e]cret`), not by excluding the file. This repo's own history includes a
  fail-open checker: `tools/mutants.py` originally counted any nonzero pytest
  exit as a kill, so usage errors (exit 4/5) would have faked whole-batch
  kills; fixed earlier (only exit 1 counts, errors invalidate the run).
- **Git history note**: the demo originally ran without git (restores were
  verified by suite rerun + tree hash). The repo is now under git; source
  state above cites the commit.
- **Spec revision 3 is a retrofit** (2026-07-27): the failure-model and
  setup-plan sections were added after implementation to comply with the
  current skill; the original setup was authorized conversationally, not via
  spec approval. The failure-mode→layer mapping was reconstructed, not
  design-driven — a fresh Tier 3 task would write it first.
- Remaining known limits (out of spec scope): not thread-safe (no locking —
  named in the failure model as the uncovered mode); a NaN-returning *clock*
  fails closed but is not rejected.
