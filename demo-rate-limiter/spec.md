# Spec: Sliding-Window Rate Limiter (Tier 3)

A library class `RateLimiter(limit, window_seconds, clock)` answering
`allow(key) -> bool`: at most `limit` allowed requests per `key` within any
sliding `window_seconds` interval. `clock` is an injected callable returning
current time in seconds (the mock boundary — no real sleeping in tests).

```gherkin
Feature: Sliding-window rate limiting per key

  Scenario: requests under the limit are allowed
    Given a limiter with limit 3 per 60 seconds
    When a key makes 3 requests at t=0
    Then all 3 return True

  Scenario: request over the limit is denied
    Given a limiter with limit 3 per 60 seconds
    And a key made 3 allowed requests at t=0
    When the key makes a 4th request at t=59
    Then it returns False

  Scenario: denied requests do not consume quota
    Given a limiter with limit 1 per 60 seconds
    And a key made 1 allowed request at t=0 and 5 denied requests at t=10
    When the window expires at t=61
    Then the next request returns True
    (denials at t=10 must not have extended or refilled anything)

  Scenario: window slides — old requests expire individually
    Given a limiter with limit 2 per 10 seconds
    And allowed requests at t=0 and t=5
    When the key requests at t=10.1
    Then it returns True   # the t=0 request left the window
    When the key requests at t=10.2
    Then it returns False  # t=5 and t=10.1 still inside

  Scenario: keys are isolated
    Given a limiter with limit 1 per 60 seconds
    And key "a" has exhausted its quota at t=0
    When key "b" requests at t=0
    Then it returns True

  Scenario: invalid construction is rejected
    When constructing with limit 0, or a negative limit, or window_seconds <= 0
    Then ValueError is raised naming the bad parameter
    (a limiter that silently never/always allows is a security bug)

  Scenario: non-finite window is rejected  [REVISION 2026-07-25: found by the
    adversarial pass — NaN slipped through the "<= 0" check and produced a
    window that never slides; inf silently disables expiry]
    When constructing with window_seconds = NaN or +/-inf
    Then ValueError is raised naming window_seconds

  Scenario: request at the exact window boundary is still limited
    [REVISION 2026-07-27: mutant M2's kill turned out to depend on hypothesis
    randomly hitting the exact boundary — no deterministic test covered it]
    Given a limiter with limit 1 per 60 seconds
    And an allowed request at t=0
    When the key requests at exactly t=60
    Then it returns False  # a hit expires only when its age EXCEEDS the window

  Scenario: non-monotonic clock does not grant extra quota
    Given a limiter with limit 1 per 60 seconds
    And an allowed request at t=100
    When the clock jumps backward and the key requests at t=50
    Then it returns False
    (clock skew must fail closed, never open)

  Scenario: limit must be a finite positive integer  [REVISION 4]
    When constructing with limit = NaN, +/-inf, a float such as 2.5, or a bool
    Then ValueError is raised naming limit
    (limit=NaN made every comparison False and the limiter allowed forever —
    the same fail-open class fixed for window_seconds in REVISION 2026-07-25,
    never swept across to the sibling parameter. limit=2.5 was not "silently
    treated as 2": len(hits) >= 2.5 is false at 2, so it allowed 3.)

  Scenario: window_seconds must be a number  [REVISION 4b]
    When constructing with window_seconds = True, "60", or None
    Then ValueError is raised naming window_seconds
    (the sweep ran one way only: window_seconds=True built a 1.0-second
    window, and "60" raised a bare TypeError from math.isfinite instead of
    naming the parameter the invalid-construction scenario promises)

  Scenario: keys are compared as exact strings  [REVISION 4b, widened in 4c]
    Given a limiter with limit 1 per 60 seconds
    When "Alice", "alice", "alice " and " " each make a request
    Then all are allowed — they are four different callers
    (every key elsewhere in the suite was lowercase and unpadded, so key
    normalisation was structurally invisible. Case was pinned in 4b and
    trimming still survived it, so padding is pinned too. A whitespace-only
    key is a valid caller by the same rule: the contract is "non-empty str",
    and deciding that " " is not a real caller is the caller's business.)

  Scenario: the sweep keeps a key whose newest hit is exactly one window old
    [REVISION 4c]
    Given a limiter with limit 1 per 60 seconds
    And another key's request at t=0 that arms the sweep, and "k" at t=1
    When any request arrives at t=61, firing the sweep
    Then "k" is still limited — its hit is exactly 60s old, not older
    (the exact-boundary scenario pins _prune's comparison; _sweep re-implements
    the same age test and nothing pinned it, so a >= there forgot a key that
    still had a live hit and reset that caller's quota)

  Scenario: concurrent commits never invert against the clock read
    [REVISION 4c]
    Given two callers whose clock reads are forced to return different values
    When the caller that read the earlier value commits second
    Then the recorded hits are still in ascending order
    (both _prune and _sweep assume that order; the lock originally covered
    check-and-append but not the clock read, and every other concurrency test
    held time constant so the whole class of ordering races was invisible)

  Scenario: key must be a non-empty string  [REVISION 4]
    When calling allow() with None, an int, bytes, or ""
    Then TypeError (wrong type) or ValueError (empty) is raised
    (CONTRACT HARDENING, not a reproduced fail-open: None as a key made every
    unidentified caller share one bucket, which limits too strictly or lets
    callers exhaust each other's quota — it never let anyone past the limit.
    Approved as a deliberate tightening for an HTTP-facing API, and recorded
    separately from the defects that were demonstrated.)

  Scenario: idle keys are forgotten — the key map is bounded  [REVISION 4]
    Given a limiter with limit 1 per 60 seconds
    And 1000 distinct keys that each made one request at t=0 and never return
    When any request arrives after a full window has elapsed
    Then the limiter retains only keys with a hit inside the current window

  Scenario: concurrent callers never exceed the limit  [REVISION 4]
    Given a limiter with limit 1 per 60 seconds
    When many threads call allow() for the same key simultaneously
    Then exactly 1 call returns True
    (read-prune-check-append was not atomic; measured 2x over-allow)
```

## Invariants (property-based)

- P1: for any request sequence on one key, allowed count within any window of
  `window_seconds` (by the times the limiter saw) never exceeds `limit`.
- P2: interleaving traffic from other keys never changes one key's outcomes.

## Must NOT do

- The limiter under test is never driven by a real clock, and no test makes
  time pass by sleeping. [REVISION 4, amended: the gate matched only `time.`
  and missed `from time import sleep`. The wording here previously claimed to
  cover "every spelling", which a regex cannot do — dynamic imports, renamed
  helpers, and a caller's own `sleep()` all escape it. The gate blocks known
  direct wall-clock imports and calls; that is its actual scope.]
  **Declared exception** [corrected in 4d]: the concurrency tests use
  `Event.wait(timeout=)` and `Thread.join(timeout=)`. Most are deadlock guards,
  but TWO are genuine wall-clock dependences and they fail in OPPOSITE
  directions, which the 4b wording got wrong by naming only the first:
  (1) the atomicity test asserts a blocked thread is still alive after 0.2s —
  spurious failure only, if a thread is starved that long;
  (2) `second_done.wait(timeout=0.3)` in the clock-ordering test is not a
  guard at all: on healthy code it ALWAYS times out (a fixed 0.3s per suite
  run), and on the mutant that moves the clock read outside the lock the kill
  depends on the second caller finishing inside that budget. Its spurious
  direction is therefore a false PASS — a surviving fail-open mutant, the
  worse direction. Measured margin is ~470x (0.06-0.63ms of 300ms), so it is
  accepted, not ignored. No limiter in any test reads a real clock.
- No unbounded memory growth. [REVISION 4: this clause used to read "from
  denied requests (denials store nothing)". Denials were never the leak;
  *allowed* requests from keys that never return were. Growth is bounded by
  the distinct keys seen within TWO windows — see the idle-keys scenario.
  REVISION 4d: this clause and the class docstring both said "one window" and
  were literally false. Because the sweep is throttled to once per window, a
  key can sit idle for just under 2W before the sweep that drops it runs. Only
  the residual-risk section had it right; the idle-keys test probed at 2W, so
  it passed under either reading and pinned neither.]

## Clock contract [REVISION 4]

`clock` MUST be monotonic (`time.monotonic`, as `examples/demo.py` uses). A
forward jump — NTP step, resumed VM — expires every hit at once and resets
every caller's quota simultaneously. That is inherent to a sliding window over
a supplied clock and is not defended against in code; it is a caller
obligation, stated here because the failure model previously implied the
non-monotonic scenario covered skew in both directions. It covers backward
skew only.

`clock` MUST also return a finite number. [REVISION 4b, corrected in 4c] A NaN
reading is recorded as a hit that can never expire: `now - nan > window` is
always false, in `_prune` **and in `_sweep`**. Revision 4b claimed the sweep
would eventually reclaim such a key; it cannot — the sweep uses the same
comparison. Measured: once a key's newest hit is NaN, the key is retained
through t=1e18 and that caller is denied forever. **This falsifies the
temporal memory bound for NaN-poisoned keys**, which is stated here rather
than left to be inferred. The third NaN injection point is the clock itself,
and it stays a caller obligation rather than a check because validating every
reading puts a branch on the hot path for a fault `time.monotonic` cannot
produce. [4d] A NaN reading also destroys the sweep throttle permanently:
`_last_sweep` becomes NaN, every subsequent comparison against it is false,
and the sweep then runs an O(distinct keys) scan on every request for the
life of the process. The 4c paragraph described the never-expiring hit as if
that were the whole mode; it is not.

`clock` is the only constructor parameter with no validation. That is
deliberate — a non-callable clock raises TypeError at the first `allow()`,
which is loud and fail-closed, not the silent acceptance the hostile-config
row is about. [4d]

`clock` MUST NOT call back into the same limiter. [REVISION 4c] The clock is
read inside the critical section, so a reentrant clock deadlocks on a
non-reentrant lock. This is the price of the fix for the ordering race and is
recorded as an obligation rather than hidden.

## Accepted residual risk [REVISION 4b]

The memory bound is **temporal, not cardinal**: keys idle for a window are
forgotten, but nothing caps how many distinct keys appear *within* one window.
An attacker who controls the key — which, per the stated deployment, is an IP
or a request header — can still drive the map arbitrarily large inside a
single window, and because the sweep is throttled to once per window the
worst-case retention is closer to two windows than one. This is accepted, not
overlooked: a cardinality cap needs an eviction policy (which caller gets
forgotten?), and evicting a live key silently resets its quota — a fail-open
worse than the memory it saves. Recorded here so the residual reads as
accepted rather than absent, in the same register as the clock contract.

## Failure model (Tier 3)

[REVISION 3, 2026-07-27: retrofitted — the skill now requires an explicit
failure model before layer selection; these modes were previously implicit
in the scenarios, Must NOTs, and adversarial pass.]

[REVISION 4, 2026-08-09, amended 4b: independent fresh-context verification
found rows below claiming coverage they did not have. The standard is now:
every covered mode must name and demonstrate an **appropriate falsification
procedure** — a test, a mutant, fault injection, a benchmark, a rollback
rehearsal, whatever actually fits the risk. Not "a test AND a mutant", which
just breeds mutants written to fill a table. A row whose catcher cannot be
shown to fail is a defect, not a mapping.]

| How this can hurt | Falsification procedure, demonstrated |
|---|---|
| over-allowing in a burst (limit not enforced) | scenario tests + P1; mutants M1/M5 killed |
| under-allowing / fail-closed drift (quota lost) | boundary scenario, demonstrated by killing M2. [4b: this row previously cited M6/M8 — M6 in fact **over**-allows, and M8 is killed by the memory row's tests. Verification also proposed a `while`→`if` mutant here; it proved EQUIVALENT, see mutants.py] |
| hostile or invalid config silently accepted | validation scenarios for limit, window_seconds AND key + adversarial pass; mutants M4/M7/M9/M15 killed |
| backward clock skew opening the gate | non-monotonic clock scenario, jump exceeding the window; mutant M10 killed |
| forward clock skew resetting all quota | **not covered — caller obligation**; see Clock contract |
| a non-finite clock reading freezing a hit in the window | **not covered — caller obligation**; see Clock contract [4b] |
| caller identity silently merged (key normalisation) | exact-strings scenario, covering case AND padding; mutants M14/M17 killed. [4c: the row previously cited case-folding only, and `key.strip()` survived it — the P2 pool held `"c "` but not `"c"`, so no two members could merge] |
| a caller's quota reset by the sweep at the exact boundary | sweep-boundary scenario; mutant M18 killed [4c] |
| concurrent commits inverted against the clock read | clock-ordering scenario (gated clock forces two callers to read different values); mutant M16 killed. [4c: the lock covered check-and-append but not the clock read. Both earlier concurrency tests held time constant, so no test could tell the two placements apart] |
| unbounded memory growth (any path) | idle-keys scenario + denials test; mutants M8/M12 killed |
| concurrent callers racing on shared state | **fault injection**: the atomicity test constructs the interleaving and kills M13 deterministically. The threaded stress test corroborates statistically (measured 5.9% per-round detection, 400 rounds) but cannot be the sole catcher — at 60 rounds the lock-removal mutant was observed surviving 1 run in 50 |
| the mutation layer reporting kills it never ran | **negative control**: a killer and a strictly-equivalent mutant of identical size under one pinned mtime; proven non-vacuous by removing the cache defence and watching the control go red [4b] |
| untested code reaching production | coverage layer, now a gate (`--cov-fail-under=100`) — it previously printed a number and could not fail |
| silent failure in production | n-a: library returns a bool the caller observes directly |

## Setup plan

[REVISION 3, 2026-07-27: retrofitted — the skill now requires dependencies
to be justified in the spec. Original setup was authorized conversationally.]

- Runtime dependencies: **none** — stdlib (`collections.deque`, `math`) suffices.
- Dev toolchain (pinned in `requirements-dev.txt`, never shipped):
  - pytest + pytest-cov + coverage — test runner and changed-line coverage
  - mypy — strict type checking
  - ruff — lint, format, and complexity budget (mccabe ≤ 8)
  - hypothesis — property-based invariants P1/P2
  - pip-audit — vulnerability audit of the pinned toolchain
  - pytest-randomly — randomized test order (suite-health layer)
- Git: repo-level; commits at each milestone; evidence binds to commit SHA.
- Files the gauntlet adds: `tools/gauntlet.sh` (entry point), `tools/mutants.py`
  (scripted manual mutation), `.github/workflows/gauntlet.yml` (CI),
  `tools/must_not_match.sh` + `tools/test_gauntlet_checks.sh` (fail-closed
  scan helper and its self-test).
- [REVISION 4] Runtime dependencies remain **none**: `threading.Lock` is
  stdlib. The coverage layer gains `--cov-fail-under=100`, making it a gate
  rather than a report.

## Explicitly out of scope [REVISION 4]

- **Retry-After / remaining-quota accessor.** `allow(key) -> bool` gives an
  HTTP frontend no way to populate `Retry-After` or `X-RateLimit-Remaining`,
  which RFC 9110 expects alongside a 429. Raised by both verification passes.
  Declined here because it changes the public API shape and the contract asks
  only to bound request frequency — recorded so the gap is visible rather than
  absent.
- **Distributed / multi-process limiting.** In-process state only.
