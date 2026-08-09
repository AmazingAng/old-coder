# Evidence Report — Sliding-Window Rate Limiter (Tier 3)

- Spec approval: **obtained** for REVISION 4 (2026-08-09) — the human approved
  each contract change item by item before implementation. Earlier revisions
  (2026-07-25, 2026-07-27) were autonomous and are still unapproved; treat
  them as the weaker part of the spec.
- Independent verification: **six fresh-context rounds**, the last against
  commit `d0b506c`. See "Independent verification" below — including what the
  final round found and what was deliberately left unfixed.
- Source state: git commit `66df5cd`; sha256 tree hash `402ed5f682f8543f` —
  reproduce both with `./tools/source_state.sh` (works from any directory;
  now includes `.github/workflows`, which decides whether the gauntlet runs
  in CI at all).
- Toolchain: pinned in `requirements-dev.txt` (local run: Python 3.14.3;
  CI runs the same gauntlet on 3.12 via `.github/workflows/gauntlet.yml`).
- Entry point: `./tools/gauntlet.sh` reruns every layer below.

All numbers are from one final fresh run of the entry point, executed
2026-08-10 after the last code edit.

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
| non-finite window is rejected | test_ratelimiter.py::test_non_finite_window_is_rejected (3 params) | pass |
| non-monotonic clock does not grant extra quota | test_ratelimiter.py::test_non_monotonic_clock_does_not_grant_extra_quota | pass |
| request at the exact window boundary is still limited | test_ratelimiter.py::test_request_at_exact_window_boundary_is_still_limited + M2 | pass |
| limit must be a finite positive integer (R4) | test_ratelimiter.py::test_limit_must_be_a_finite_positive_integer (5 params) + M9 | pass |
| window_seconds must be a number (R4b) | test_ratelimiter.py::test_window_seconds_must_be_a_number (3 params) + M15 | pass |
| key must be a non-empty string (R4) | test_ratelimiter.py::test_key_must_be_a_non_empty_string (4 params) | pass |
| keys are compared as exact strings (R4b/4c) | test_ratelimiter.py::test_keys_are_compared_as_exact_strings + M14/M17 | pass |
| sweep keeps a key exactly one window old (R4c) | test_ratelimiter.py::test_sweep_keeps_a_key_whose_newest_hit_is_exactly_window_old + M18 | pass |
| a key is dropped by the first sweep after one idle window (R4f) | test_ratelimiter.py::test_a_key_is_dropped_by_the_first_sweep_after_one_idle_window + M23 | pass |
| the key map is bounded by two windows, not one (R4e) | test_ratelimiter.py::test_the_memory_bound_is_two_windows_not_one | pass |
| nothing is reclaimed while traffic is silent (R4e) | test_ratelimiter.py::test_memory_is_not_reclaimed_while_traffic_is_silent | pass |
| the sweep is throttled to at most once per window (R4e) | test_ratelimiter.py::test_the_sweep_is_throttled_to_once_per_window + M19/M21 | pass |
| the first call always sweeps (R4e) | test_ratelimiter.py::test_the_first_call_always_sweeps + M22 | pass |
| a backward clock jump does not suspend reclamation (R4e) | test_ratelimiter.py::test_backward_clock_skew_does_not_suspend_the_sweep + M20 | pass |
| idle keys are forgotten — the key map is bounded (R4) | test_ratelimiter.py::test_idle_keys_are_forgotten_key_map_is_bounded + M12 | pass |
| concurrent callers never exceed the limit (R4) | test_ratelimiter.py::test_concurrent_callers_never_exceed_the_limit (statistical; see notes) | pass |
| concurrent commits never invert against the clock read (R4c) | test_ratelimiter.py::test_clock_is_read_inside_the_critical_section + M16 | pass |
| Invariant P1 (window count ≤ limit) | test_properties.py::test_p1_allowed_count_within_any_window_never_exceeds_limit | pass |
| Invariant P2 (key independence) | test_properties.py::test_p2_other_keys_traffic_never_changes_one_keys_outcomes | pass |
| Must NOT: denials store nothing (no memory growth) | test_ratelimiter.py::test_must_not_denials_store_nothing + M8 | pass |
| Must NOT: the limiter is never driven by a real clock | layer: must-not scan in `tools/gauntlet.sh` over tests/ → no matches | pass |
| failure-model row: allow() is atomic | test_ratelimiter.py::test_allow_is_atomic_a_second_caller_cannot_interleave + M13 | pass |

## Gauntlet (final fresh run: `./tools/gauntlet.sh`)

| Layer | Command | Result |
|---|---|---|
| Checker self-test | `sh tools/test_gauntlet_checks.sh` (first layer; asserts the must-not scan fails on a planted pattern, passes on a clean tree, and fails closed with a distinct rc 2 when the scan itself breaks) | 3/3 expectations ok |
| Mutation harness negative control | `python tools/mutants.py --negative-control` (a killer and a strictly-equivalent mutant of identical size under one pinned mtime) | C1 KILLED, C2 SURVIVED — ok |
| Tests | `pytest -q --cov=ratelimiter` | 41 passed, 0 failed |
| Types | `mypy src tests examples tools` (strict) | 0 errors in 6 files |
| Lint + format + complexity | `ruff check . && ruff format --check .` (mccabe ≤ 8) | 0 warnings, 8 files formatted |
| Changed-line coverage | `pytest --cov … --cov-fail-under=100` | 49/49 statements, 20/20 branches (100%). **This layer is a gate**; before 2026-08-09 it printed a percentage and exited 0 no matter how far coverage fell |
| Mutation | `python tools/mutants.py` (manual, scripted; only pytest exit 1 counts as a kill; `__pycache__` cleared and `PYTHONDONTWRITEBYTECODE` set per mutant) | 22/22 killed |
| Property-based | hypothesis, 2 properties | 100 examples each, 0 falsified |
| Real execution | `python examples/demo.py` (real `time.monotonic`) | burst of 5 → `[True, True, True, False, False]`; other key unaffected; allowed again after window |
| Supply chain | `pip-audit -r requirements-dev.txt` | no known vulnerabilities; runtime dependencies: **none** (stdlib only; `threading` is stdlib) |
| Secret scan | must-not scan in `tools/gauntlet.sh` over src, tests, tools, examples, spec.md, pyproject.toml, requirements-dev.txt and `../.github` | clean, no matches |
| License check | — | n-a: zero runtime dependencies, nothing redistributed beyond this repo's own MIT code |
| Suite health | pytest-randomly (order shuffled every run) | 41 passed in randomized order, 10/10 consecutive runs |

## Layer attribution

- Property suite alone: **3/22** mutants killed (M1, M3, M5). The properties
  are single-threaded and never construct an invalid limiter, so validation,
  key-identity, memory, sweep and concurrency mutants are all outside their
  reach by construction.
- Scenario suite alone: **22/22**. The headline mutation score is carried
  entirely by the scenario tests.

## Skipped layers

- Tool-based mutation (mutmut): unverified compatibility with Python 3.14;
  replaced with the scripted manual procedure (`tools/mutants.py`, 22 mutants).
- Shell lint (shellcheck) for the four scripts that implement half the gates:
  **not run**, no tool installed. Every Python file gets three static layers
  and the shell gets none. Known gap, raised by verification round 4.

## Independent verification

Six rounds, each a fresh agent context given only the task contract, the
approved SPEC, the repository at an exact source state, and the gauntlet entry
point — never the builder's reasoning, and never the draft of this report.
Each ran against a different commit; a round that raised a finding never
judged its own fix.

| Round | Commit | Behavioural defects | Description / mapping defects | Verdict |
|---|---|---|---|---|
| 1 (two arms) | `9540d72` | 3 material, found by both arms independently | 2 | failed |
| 2 | `e677832` | 1 material (the mutation harness) | 5 | failed |
| 3 | `e210594` | 1 material (lock scope) | 6 | failed |
| 4 | `49afb2b` | 1 (backward skew) | 3 | passed |
| 5 | `d65acbe` | 0 | 6 (1 rated material) | failed |
| 6 | `d0b506c` | 1 gap (sweep threshold magnitude) | 6 | failed |

What rounds 1–3 found, none of which the ten green layers could reach: a
one-shot-key memory leak usable as a remote DoS against the component meant
to *prevent* one; `limit=NaN`/`inf` producing a limiter that always allows;
2× over-allow under threads; and a mutation runner reporting kills for
mutants it never executed.

Rounds 4–6 found one behavioural gap and a steady stream of inaccuracies in
the prose — and **two of those were introduced by the round that fixed the
previous one**. That is the honest shape of the result: verification does not
converge just because one round comes back clean.

**Verification stopped after round 6, deliberately.** A rule of "fix every
finding, then start a new verifier" only terminates when a round returns the
empty set, and prose has no such fixpoint. The findings below were fixed after
round 6 and are therefore **not independently verified**:

- the sweep threshold magnitude test and mutant M23;
- the vacuous-pass assertion added to the clock-ordering test;
- the six prose corrections listed in commit `66df5cd`.

## Honest notes

- **The A/B experiment that started this failed.** The design was to plant a
  defect in one copy and verify a clean copy as a false-positive control. The
  "clean" arm was not clean: it independently invented the exact mutation that
  had been planted in the other arm and reported it as a real finding, which
  it was. The planted defect only made an existing spec/test hole explicit,
  so the arms were not distinguishable and no false-positive rate could be
  measured. This is an exploratory adversarial case study, not a successful
  A/B benchmark, and nothing here supports a general claim about verifier
  accuracy. Two false positives did occur, both caused by the harness feeding
  a subdirectory instead of the repository and a tree polluted by an editable
  install — verifier noise was a function of input quality, on n=2.
- **All six verifier rounds ran on the same model as the builder.** Their
  convergence shows the findings are reproducible, not that they are
  independent of model bias. The correlation this breaks is context, not
  model.
- **The concurrency scenario's stress test is statistical.** Per-round
  detection against the real source mutant measured 3.7% on this machine
  (an earlier 5.9% in this report came from a Python replica rather than the
  mutant); at 400 rounds the miss probability is ~3e-7, and the rate is
  machine-dependent. It is deliberately **not** the catcher for that row —
  the deterministic fault-injection test is, and it kills M13 5/5. At the
  original 60 rounds the lock-removal mutant was observed surviving 1 run in
  50, which is why the row was restructured.
- **Two tests depend on real wall-clock time**, declared in spec.md: one
  asserts a blocked thread is still alive after 0.2s (spurious direction:
  failure) and one waits up to 0.3s for a racing caller (spurious direction:
  a false PASS, i.e. a surviving fail-open mutant — the worse direction).
  Measured margin ~470×.
- **Equivalent mutants, classified rather than killed**: a `while`→`if`
  under-prune proposed by verification as a defect proved equivalent under a
  monotone clock (0 divergences over 200k randomized sequences), as did
  several sweep-timing variants. Killing them would need tests asserting
  non-behaviour, which anti-gaming rule 4 forbids.
- **The historical 8/8 mutation figure, stated precisely.** The runner used
  before 2026-08-09 was vulnerable to `.pyc` reuse between same-size mutants
  written in the same second, and exactly one adjacent pair could collide
  (M4/M5, both 1675 bytes). Re-derived on the historical source under a sound
  procedure, all 8 are genuinely killed, M5 included. The published figure is
  therefore **correct in outcome even though the procedure that produced it
  was unsound**; whether that archived run took the collision path cannot be
  determined, and does not change the number.
- **A negative control that was itself vacuous.** The first version of the
  mutation harness's negative control waited for two writes to land in the
  same second rather than pinning the mtime, and passed with the defence
  removed. It was caught only because the control was tested for its ability
  to fail. Its second version used a control mutant that was not strictly
  equivalent. Both are recorded because "prove the checker can fail" is a
  rule this project states, and it took two attempts to satisfy it here.
- **Three defects were introduced by fixes** in this sequence: the lock added
  in REVISION 4 did not cover the clock read (found in round 3); the NaN
  paragraph corrected in 4d contained a fresh false claim (round 5); and the
  "just under 2W" bound written in 4e was wrong (round 6).
- **Layer attribution moved during the work.** Widening the property
  strategies to answer one finding *weakened* the property layer — the
  fail-open mutant M5 stopped being killed by the properties, because with
  258 possible keys and limits up to 20 hypothesis almost never drove a key
  to its limit. Re-tuned to 12 keys and limits 1–5, measured rather than
  guessed. Without the Tier 3 attribution requirement this regression would
  have been invisible: the full suite stayed green throughout.
- **Known gaps left open**: the memory bound is temporal, not cardinal —
  unbounded distinct keys *within* one window is accepted residual risk;
  forward clock skew, NaN clock readings and reentrant clocks are caller
  obligations, not defended in code; there is no `Retry-After` accessor; the
  shell scripts have no lint layer; and evidence is generated on Python 3.14
  while CI gates on 3.12.
- **Spec revisions 2026-07-25 and 2026-07-27 remain unapproved**, and the
  revision-3 failure model was a retrofit reconstructed after implementation
  rather than written before it.
- **Git history note**: the demo originally ran without git. The repo is now
  under git; source state above cites the commit.
