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
```

## Invariants (property-based)

- P1: for any request sequence on one key, allowed count within any window of
  `window_seconds` (by the times the limiter saw) never exceeds `limit`.
- P2: interleaving traffic from other keys never changes one key's outcomes.

## Must NOT do

- No real time.sleep / wall-clock dependence in tests.
- No unbounded memory growth from denied requests (denials store nothing).

## Failure model (Tier 3)

[REVISION 3, 2026-07-27: retrofitted — the skill now requires an explicit
failure model before layer selection; these modes were previously implicit
in the scenarios, Must NOTs, and adversarial pass.]

| How this can hurt | Layer that catches it |
|---|---|
| over-allowing in a burst (limit not enforced) | scenario tests + P1 + mutants M1/M5 |
| under-allowing / fail-closed drift (quota lost) | boundary scenario + mutants M6/M8 (P1 is one-sided and cannot catch this) |
| hostile or invalid config silently accepted | validation scenarios + adversarial pass + mutants M4/M7 |
| clock skew opening the gate | non-monotonic clock scenario |
| memory growth from denials | Must NOT test + mutant M8 |
| concurrent callers racing on shared state | **not covered — known limit**; single-threaded use only |
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
  (scripted manual mutation), `.github/workflows/gauntlet.yml` (CI).
