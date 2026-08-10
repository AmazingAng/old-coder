# Spec: Sliding-Window Rate Limiter (Tier 3)

A library class `RateLimiter(limit, window_seconds, clock)` answering
`allow(key) -> bool`: at most `limit` allowed requests per `key` within any
sliding `window_seconds` interval. `clock` is an injected callable returning
current time in seconds (the mock boundary — no real sleeping in tests).
Intended deployment: in front of a public HTTP API, so callers are untrusted
and the key space is attacker-controlled.

This document is the contract. How each clause was arrived at — including the
defects that six rounds of independent verification found and the two that a
fix round introduced — is in `evidence.md`'s honest notes and in git history,
deliberately not here.

## Behaviour

```gherkin
Feature: Sliding-window rate limiting per key

  Scenario: requests under the limit are allowed
    Given a limiter with limit 3 per 60 seconds
    When a key makes 3 requests at t=0
    Then all 3 return True

  Scenario: request over the limit is denied
    Given a limiter with limit 3 per 60 seconds and 3 allowed requests at t=0
    When the key makes a 4th request at t=59
    Then it returns False

  Scenario: denied requests do not consume quota
    Given a limiter with limit 1 per 60 seconds
    And 1 allowed request at t=0 and 5 denied requests at t=10
    When the window expires at t=61
    Then the next request returns True

  Scenario: window slides — old requests expire individually
    Given a limiter with limit 2 per 10 seconds and requests at t=0 and t=5
    When the key requests at t=10.1
    Then it returns True   # the t=0 request left the window
    When the key requests at t=10.2
    Then it returns False  # t=5 and t=10.1 are still inside

  Scenario: keys are isolated
    Given a limiter with limit 1 per 60 seconds and key "a" exhausted at t=0
    When key "b" requests at t=0
    Then it returns True

  Scenario: request at the exact window boundary is still limited
    Given a limiter with limit 1 per 60 seconds and an allowed request at t=0
    When the key requests at exactly t=60
    Then it returns False  # a hit expires only when its age EXCEEDS the window

  Scenario: non-monotonic clock does not grant extra quota
    Given a limiter with limit 1 per 60 seconds and a request at t=100
    When the clock jumps backward by more than the window and the key requests
    Then it returns False  # skew must fail closed, never open

  Scenario: invalid construction is rejected
    When constructing with limit 0, a negative limit, or window_seconds <= 0
    Then ValueError is raised naming the bad parameter
    (a limiter that silently never or always allows is a security bug)

  Scenario: limit must be a finite positive integer
    When constructing with limit = NaN, +/-inf, a float such as 2.5, or a bool
    Then ValueError is raised naming limit
    (every comparison against NaN is false, so the limiter allowed forever)

  Scenario: window_seconds must be a positive finite number
    When constructing with window_seconds = NaN, +/-inf, True, "60", or None
    Then ValueError is raised naming window_seconds

  Scenario: key must be a non-empty string
    When calling allow() with None, an int, bytes, or ""
    Then TypeError (wrong type) or ValueError (empty) is raised
    (a missing HTTP header arriving as None must not become one shared bucket
    for every unidentified caller)

  Scenario: keys are compared as exact strings
    Given a limiter with limit 1 per 60 seconds
    When "Alice", "alice", "alice " and " " each make a request
    Then all are allowed — they are four different callers

  Scenario: concurrent callers never exceed the limit
    Given a limiter with limit 1 per 60 seconds
    When many threads call allow() for the same key simultaneously
    Then exactly 1 call returns True

  Scenario: concurrent commits never invert against the clock read
    Given two callers whose clock reads return different values
    When the caller that read the earlier value commits second
    Then the recorded hits are still in ascending order
    (both pruning and sweeping assume that order)

  Scenario: idle keys are forgotten — the key map is bounded
    Given 1000 distinct keys that each made one request at t=0 and never return
    When any request arrives after a full window has elapsed
    Then the limiter retains only keys with a hit inside the current window

  Scenario: a key is dropped by the first sweep after one idle window
    Given "armer" and "idle" both at t=0
    When a request arrives at t=61, firing the sweep
    Then "idle" is gone  # the idle threshold is one window, not more

  Scenario: the sweep keeps a key whose newest hit is exactly one window old
    Given "other" at t=0 arming the sweep, and "k" at t=1
    When a request arrives at t=61, firing the sweep
    Then "k" is still limited — its hit is exactly 60s old, not older

  Scenario: the key map is bounded by two windows, not one
    Given "armer" at t=0 and "idle" at t=1, then a request at t=60.9
    When a request arrives at t=100 — "idle" has been idle for 99s
    Then "idle" is still retained; only at t=121 is it forgotten
    (the sweep is throttled, so residency reaches 2W before the dropping sweep)

  Scenario: nothing is reclaimed while traffic is silent
    Given 50 one-shot keys at t=0
    When the clock advances by ~166,000 windows and no request is made
    Then all 50 are still resident; the map shrinks only on the next request

  Scenario: the sweep is throttled to at most once per window
    Given a limiter with a 60-second window and a request at t=0
    When further requests arrive at t=30 and at t=60
    Then no further sweep has run; the sweep at t=61 does run

  Scenario: the first call always sweeps
    Given a fresh limiter with a 60-second window
    When the very first request arrives at t=30
    Then a sweep has run

  Scenario: a backward clock jump does not suspend reclamation
    Given a limiter armed at t=1,000,000
    When the clock jumps back to 0 and 200 one-shot keys arrive over 400s
    Then the sweep still runs and the map does not grow without bound
```

## Invariants (property-based)

- **P1**: for any request sequence on one key, the allowed count within any
  window of `window_seconds` never exceeds `limit`.
- **P2**: interleaving traffic from other keys never changes one key's outcomes.

## Must NOT do

- **No real clock in tests.** The limiter under test is never driven by a real
  clock, and no test makes time pass by sleeping. The gate that enforces this
  is a regex over `tests/`; its scope is known direct wall-clock imports and
  calls. Dynamic imports, renamed helpers and a caller's own `sleep()` escape
  it, and the gate does not claim otherwise.

  *Declared exception.* Two assertions in the concurrency tests do depend on
  real elapsed time, and they fail in opposite directions:
  (1) the atomicity test asserts a blocked thread is still alive after 0.2s —
  spurious failure only; (2) the clock-ordering test waits up to 0.3s for a
  racing caller — on healthy code that wait always times out, and its spurious
  direction is a false PASS, i.e. a surviving fail-open mutant. Measured margin
  ~470×. Accepted deliberately: the alternative is a test that can hang.

- **No unbounded memory growth.** Growth is bounded by the distinct keys seen
  in the **two** windows preceding the most recent request. Precisely: a key is
  resident at an age of at most exactly 2W whenever a request is observed, and
  the sweep that drops it runs strictly later than 2W after its last hit. The
  qualifier is load-bearing — sweeping happens only inside `allow()`, so while
  traffic is silent nothing is reclaimed at all and the peak resident set is
  not released until traffic resumes.

## Clock contract

`clock` is a caller obligation on three axes. None is checked in code, because
each check would put a branch on the hot path for a fault the recommended
clock cannot produce.

- **Monotonic** (`time.monotonic`, as `examples/demo.py` uses). A forward jump
  — NTP step, resumed VM — expires every hit at once and resets every caller's
  quota simultaneously. That is inherent to a sliding window over a supplied
  clock. Backward skew *is* handled: it fails closed for quota, and the sweep
  re-arms rather than suspending.
- **Finite.** A NaN reading is recorded as a hit that can never expire, in
  pruning or in sweeping, so that key is retained forever and its caller is
  denied forever — which suspends the memory bound for that key. A NaN also
  costs one extra unthrottled sweep; the throttle re-anchors on the next
  finite reading.
- **Non-reentrant.** The clock is read inside the critical section, so a clock
  that calls back into the same limiter deadlocks.

`clock` is also the one constructor parameter with no validation: a
non-callable clock raises TypeError at the first `allow()`, which is loud and
fail-closed rather than silently accepted.

## Accepted residual risk

The memory bound is **temporal, not cardinal**. Keys idle for a window are
forgotten, but nothing caps how many distinct keys appear *within* one window,
so an attacker controlling the key can still drive the map arbitrarily large
inside a single window. Accepted, not overlooked: a cardinality cap needs an
eviction policy, and evicting a live key silently resets its quota — a
fail-open worse than the memory it saves.

## Failure model (Tier 3)

Every covered mode names a **falsification procedure that has been
demonstrated to fail** — a test, a mutant, fault injection, whatever fits the
risk. Not "a test AND a mutant", which only breeds mutants written to fill a
table. A row whose catcher cannot be shown to fail is a defect, not a mapping.

| How this can hurt | Falsification procedure, demonstrated |
|---|---|
| over-allowing in a burst | scenario tests + P1; M1/M5 killed |
| under-allowing / quota lost | boundary scenario; M2 killed (P1 is one-sided and cannot see this) |
| hostile or invalid config accepted | validation scenarios for limit, window_seconds and key; M4/M7/M9/M15 killed |
| backward clock skew opening the gate | non-monotonic scenario, jump exceeding the window; M10 killed |
| backward skew suspending reclamation | backward-jump scenario; M20 killed |
| forward skew resetting all quota | **not covered — caller obligation** |
| a non-finite clock reading freezing a hit | **not covered — caller obligation** |
| caller identity merged by normalisation | exact-strings scenario, case and padding; M14/M17 killed |
| quota reset by the sweep at the boundary | sweep-boundary scenario; M18 killed |
| the retention bound silently inflating | first-sweep scenario; M23 killed (the boundary was pinned long before the magnitude was) |
| unbounded memory growth (any path) | idle-keys + silent-traffic scenarios; M8/M12 killed |
| the sweep degrading to an O(keys) scan | throttle + first-call scenarios; M19/M21/M22 killed |
| concurrent callers racing on shared state | **fault injection**: the atomicity test constructs the interleaving and kills M13 deterministically. The threaded stress test only corroborates — it is statistical (see evidence.md) |
| commits inverted against the clock read | clock-ordering scenario with a gated clock; M16 killed |
| the mutation layer reporting kills it never ran | **negative control**: a killer and a strictly-equivalent mutant of identical size under one pinned mtime, proven non-vacuous by removing the defence |
| untested code reaching production | coverage layer, a gate at `--cov-fail-under=100` |
| silent failure in production | n-a: the library returns a bool the caller observes directly |

## Setup plan

- Runtime dependencies: **none** — `collections.deque`, `math` and
  `threading.Lock` are stdlib.
- Dev toolchain (pinned in `requirements-dev.txt`, never shipped): pytest +
  pytest-cov + coverage (tests and changed-line coverage), mypy (strict types),
  ruff (lint, format, mccabe ≤ 8), hypothesis (P1/P2), pip-audit (toolchain
  vulnerabilities), pytest-randomly (suite health).
- Git: repo-level; commits at each milestone; evidence binds to a commit SHA.
- Files the gauntlet adds: `tools/gauntlet.sh` (entry point), `tools/mutants.py`
  (scripted mutation + its negative control), `tools/must_not_match.sh` and
  `tools/test_gauntlet_checks.sh` (fail-closed scan helper and its self-test),
  `tools/source_state.sh`, `.github/workflows/gauntlet.yml` (CI).

## Explicitly out of scope

- **Retry-After / remaining-quota accessor.** `allow(key) -> bool` gives an
  HTTP frontend no way to populate `Retry-After` or `X-RateLimit-Remaining`,
  which RFC 9110 expects alongside a 429. Declined: it changes the public API
  shape, and the contract asks only to bound request frequency. Recorded so
  the gap is visible rather than absent.
- **Distributed / multi-process limiting.** In-process state only.

## Revision history

Revisions 1–3 (2026-07-25 → 07-27) were made autonomously during the original
build and were never human-approved; the failure model in revision 3 was
retrofitted after implementation. Revision 4 and its amendments (2026-08-09 →
08-10) were approved item by item before implementation, and each amendment
answers a specific finding from an independent verification round. The
per-revision forensics live in `evidence.md` and in git.
