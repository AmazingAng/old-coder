---
name: old-coder
description: Evidence-first development — surround the implementation with an executable spec and a gauntlet of constraints (tests, types, coverage, mutation) so line-by-line review becomes optional. Use when the user explicitly asks for high-assurance or evidence-first work ("reliable", "TDD", "prove it works", "I won't read the code"), or when the change touches high-stakes domains (money, auth, data loss, concurrency, public API). For routine changes where the user just wants normal tests, write good tests directly instead of invoking this loop.
---

# Old Coder: Reliable Coding Under Constraint and Test

The human will NOT read your implementation. Their confidence comes entirely from
two artifacts you produce: (1) an **executable specification** they approve before
you write code, and (2) an **evidence report** proving the code ran the gauntlet.
Your job is to make those two artifacts trustworthy enough that line-by-line
review becomes optional within the spec's boundaries.

This inverts the normal review model: **trust moves from inspection to
constraints.** Be honest about what that buys: the gauntlet turns the
constraints the spec expresses into executable evidence — it cannot show the
spec expresses everything that matters, and it is not self-authenticating,
because a checker can be unsound and a mapping can claim more than it
demonstrates. That is exactly why the human approves the
SPEC (the one artifact that breaks the everything-authored-by-the-same-agent
correlation), and why EVIDENCE reports layered, auditable confidence, never
absolute proof. Every shortcut you take against the gauntlet destroys the only
basis of trust.

**Composition with `old-coder-api`:** when both skills apply, this skill owns
workflow order, SPEC approval, the gauntlet, and EVIDENCE; `old-coder-api` owns
the HTTP/JSON contract. Run its scope check and API gates while drafting SPEC,
turn the surviving constraints and risks into acceptance criteria and checks,
then map those checks into EVIDENCE. Do not run two parallel workflows.

## The Loop

```
SPEC → (human approves spec, not code) → RED → GREEN → REFACTOR → GAUNTLET → EVIDENCE
                                          ↑_____________________|
                                              repeat per behavior
```

### 1. SPEC — the only thing the human reads before code

Turn the request into **executable acceptance criteria** before touching
implementation files:

- Write behaviors as Gherkin-style scenarios or a named test list — concrete
  inputs, concrete expected outputs, edge cases, and error cases. "Handles bad
  input" is not a spec; `divide(1, 0) raises ZeroDivisionError with message X` is.
- Include what the change must NOT do (invariants that must survive: existing
  tests, public API signatures, performance budgets if stated). These negative
  constraints are contract clauses like any scenario: each must end up mapped
  in EVIDENCE to a test, a gauntlet layer, or an explicit skipped-with-reason
  line — never silently absent from the mapping.
- The spec doubles as the authorization point: include the **setup plan** —
  tools to install, git usage (init? checkpoint commit cadence?), files the
  gauntlet will add **by path**, and **every new dependency with a one-line
  justification** (prefer the standard library and deps already present; an
  unjustified package is a spec defect) — so approving the spec authorizes the
  environment changes in one step instead of N interruptions, and the human can
  veto a risky package before it is ever installed.
- Show the spec to the human in plain language and get approval **before writing
  implementation**. In autonomous mode, state the spec in your response and
  proceed — but the correlation-breaking review never happened, so EVIDENCE
  must record `spec approval: not obtained (autonomous run)` and claim
  correspondingly lower confidence; the spec becomes the artifact the human
  reviews after the fact.
- **An answer to a question is not an approval.** If you asked the human to
  decide something, they answered that question and nothing else. Their answer
  is an INPUT to the spec, and it CHANGES the spec — so any approval you held
  before the question is approval of a document that no longer exists. Questions
  and approval are two exchanges, in that order: fold the answers in, say what
  changed, show the revised spec, ask again. If you cannot quote the words that
  approved THIS spec, you do not have approval — an answer to your question, a
  "go ahead" about some other step, silence, and the request that started the
  task are none of them approval. The recommended-option shape makes this easy
  to get wrong: when the human picks the options you recommended, the spec looks
  unchanged and consent looks implied, and neither is true.
- The spec is append-only during the task. If implementation reveals the spec was
  wrong, say so explicitly and revise it visibly — never silently drift.
- **Write the spec to a file and name it by absolute path.** A relative path is
  not clickable in a terminal, so the human cannot open the one artifact they
  are being asked to approve. Same for EVIDENCE when you get there. The SPEC
  and Gherkin templates are in `references/templates.md`.
- **Commit the spec at approval** where the repo's git conventions allow it —
  the setup plan is where that was authorized. Once the approved spec is a
  commit, later drift is literally a `git diff`. Without a durable spec, a
  compaction loses the approved contract while the code it authorized remains,
  and nobody can check whether a scenario was quietly dropped from the EVIDENCE
  mapping.

### 2. RED — prove each test can fail

Write the test for one behavior. **Run it and watch it fail** before writing the
implementation. A test you never saw fail proves nothing — it may be testing
nothing. Details that matter in practice:

- If the module under test doesn't exist yet, create a stub that raises
  (e.g. `NotImplementedError`) so the test fails on behavior, not on import —
  a collection error is a weaker RED than an assertion failure.
- Related behaviors may share one RED run, as long as each new test is
  individually observed failing.
- If a new test passes immediately, it is either vacuous (fix it) or the
  behavior already exists. **Don't just assert which — prove it**: break the
  implementation with a one-off throwaway mutant, watch the test fail, restore.
  Then record it as pre-existing behavior kept as regression armor.

### 3. GREEN — minimal implementation

Write the least code that makes the failing test pass. Run the full suite, not
just the new test.

### 4. REFACTOR — clean up under green, assertions frozen

Minimal code is often ugly code. While the suite is green, improve names,
extract duplication, and simplify structure. What is frozen is **behavioral
assertions**, not test files wholesale:

- Implementation refactors touch no test files at all.
- Test-structure refactors (extracting helpers and fixtures, deduplicating
  setup) are allowed as a **separate step**: assertions unchanged, suite green
  before and after, then rerun mutation to confirm the restructured tests
  still kill — a refactor that blunts the tests is a silent hole in the
  gauntlet.
- Anything that requires editing an assertion isn't refactoring, it's a
  behavior change and belongs back in SPEC.

Run the suite after each refactor. Repeat RED→GREEN→REFACTOR per behavior.

### 5. GAUNTLET — the constraint stack

After all spec behaviors are green, run every applicable layer. Scale to the task
(see "Calibration"), but never skip a layer silently — if a layer doesn't apply
or a tool is unavailable, record that in the evidence report with the reason.

| Layer | What it catches | How |
|---|---|---|
| Full test suite | regressions | project's test command, zero NEW failures (baseline note below) |
| Static types | whole classes of bugs | tsc / mypy / etc., zero new errors |
| Lint + format | latent bugs, drift | project's linter, zero new warnings |
| Coverage on changed lines | untested code paths | every changed/added line executed by a test; branch coverage where the tool supports it. Global % is vanity — changed-line coverage is the constraint. **This layer must exit nonzero when its threshold is missed** (`--cov-fail-under`, `diff-cover --fail-under`, equivalent): a layer that prints a percentage and exits 0 is a report, not a gauntlet layer, and it will sit there green while coverage falls |
| Mutation testing | tests that assert nothing | **prefer the project's mutation tool** (mutmut, cosmic-ray, Stryker, PIT…), which generates mutants from the syntax tree and cannot silently skip one. No tool available? Manual mutation, per `references/gauntlet.md` — introduce 3–5 plausible bugs one at a time; the suite must kill every one; restore after. A hand-rolled runner must **prove it executed each mutant**: a runner that can report a kill it never ran inflates the score and no red gauntlet will ever surface it |
| Property-based tests | edge cases you didn't imagine | for parsing, math, serialization, anything with invariants (round-trip, idempotence, ordering) — add hypothesis/fast-check properties |
| Complexity budget | unmaintainable output | new functions small and single-purpose; if a function needs a paragraph to explain, split it |
| Real execution | "passes tests, doesn't run" | actually run the app/CLI/endpoint once on a realistic input, not only the test harness |
| Supply chain & secrets | vulnerable/unnecessary deps, leaked credentials | when the dependency set changed: audit it (pip-audit / npm audit / govulncheck / cargo-audit) and check licenses; scan the diff for secrets; every new dependency must trace back to its SPEC justification. Also eyeball the capability diff: did the change start using network / subprocess / filesystem / env it didn't before? |
| Suite health | flaky or order-dependent tests | run the suite in randomized order (pytest-randomly etc.); repeat suspected flakes. Every EVIDENCE number rests on the suite being deterministic — a flaky suite quietly invalidates the report |

Baseline note — on a repo with pre-existing failures, record the baseline
first (which tests already fail, verbatim) and hold the line at zero NEW
failures. Fixing unrelated pre-existing failures is scope creep: surface them,
don't silently "improve" them.

Mutation caveat — **kills are attributed to whichever test fails first**, so a
7/7 kill score validates the suite as a whole, not every layer in it. In Tier 3,
rerun the mutants against the property suite alone before claiming the
properties verify anything; survivors there mean the invariants have blind
spots (a common one: a one-sided invariant like "never exceeds limit" cannot
catch fail-closed bugs — pair it with the opposite bound).

Checker note — the gauntlet is only as trustworthy as its checkers, and the
dangerous checker failure is fail-open: nothing crashes, the layer prints pass.
Off-the-shelf tools (pytest, mypy, tsc…) have earned their failure behavior;
home-grown checks — grep gates, custom scripts, the manual mutation runner —
have not, so two rules apply to them: (1) **fail closed** — a crash, an
unreadable input, an unexpected exit code, or an item silently skipped inside
gate code is a hard failure of the layer, never a pass; no `|| true`, no
`2>/dev/null`, no bare fallthrough. (2) **Prove it can fail before trusting
its pass**: run it once against a known-bad input (a negative control) and
watch it fail — the RED principle applied to checkers, exactly like the
throwaway mutant for an immediately-passing test. Record the control in
EVIDENCE. Be precise about what that buys: **a negative control proves one
known-bad case reaches the checker's failure path. It does not prove the
checker recognizes every violation of the constraint it claims to enforce.**
A grep gate can fail closed perfectly and still guard a spelling rather than
a behavior. When the gate's coverage is narrower than the rule it serves, say
so where the rule is written, rather than letting the rule imply more.

Prove a negative control is itself non-vacuous the same way you prove a test:
temporarily remove or break the defence it validates, and watch the control go
red. A control that passes with the defence removed is measuring nothing —
this is a one-time proof, not a permanent extra layer.

Equivalent-mutant note — with a mutation tool, a survivor is not automatically
a failure: some mutants are semantically equivalent to the original and cannot
be killed. Classify such survivors as "equivalent, because <reason>" in
EVIDENCE rather than adding a meaningless test to kill them — that would
violate anti-gaming rule 4. Hand-written mutants (the manual procedure) get no
such excuse: you chose them, so choose real bugs.

### 6. EVIDENCE — the only thing the human reads after code

End with a report the human can trust without opening a single source file
(template in `references/templates.md`):

- The approved spec, with each behavior mapped to the test that verifies it.
- Each gauntlet layer: the command run, and its actual result (pasted numbers,
  not adjectives). "All 47 tests pass, changed-line coverage 100% (31/31 lines),
  5/5 manual mutants killed" — never "tests look good".
- All numbers must come from one final fresh run executed after the last code
  edit — results from mid-task runs are stale and must not be reported.
- The report must be reproducible from the repo alone: every command it cites
  (including the mutation script) must exist as a persisted file in the repo,
  not in a scratch directory or only in the conversation. Reproducible means:
  dev-tool versions pinned or recorded, one entry-point command that reruns
  every layer, and the source state identified (commit SHA, or a source-tree
  hash when git is absent).
- Layers skipped, and why.
- Anything that failed and how it was resolved, honestly. A gauntlet you passed
  on the first try and a gauntlet you fixed your way through are equally fine;
  a gauntlet you quietly weakened is the only failure.

## Anti-Gaming Rules (absolute)

The gauntlet only creates trust if it cannot be gamed. These are hard rules:

1. **Never weaken a test to make it pass.** Don't broaden assertions, add skips,
   raise tolerances, or delete a failing test. If a test seems wrong, that's a
   spec conversation — surface it, don't bury it.
2. **Never edit a test and the implementation in the same step to reach green.**
   Change one, run, then the other. Simultaneous edits let you accidentally
   redefine correctness to match your bug.
3. **Never mock the unit under test** or mock so much that the test only
   exercises the mocks. Mock boundaries (network, clock, filesystem), not logic.
4. **Never chase the coverage number.** Coverage is a detector of untested code,
   not a target. A test added only to touch lines, with no meaningful assertion,
   is gaming — mutation testing exists precisely to catch this, including yours.
5. **Never report a layer you didn't run.** An honest "skipped: no mutation tool
   in this environment, did manual mutation instead" preserves trust; an
   invented result destroys the entire scheme.
6. **Failing gauntlet blocks done.** You are not finished while any layer fails.
   If you're genuinely blocked, report the failure verbatim as the outcome.

## Calibration

Scale effort to blast radius, and say which tier you chose:

- **Tier 1 — trivial** (typo, comment, config value): full suite + lint. No new
  tests required, but state why the change is untestable or already covered.
- **Tier 2 — normal** (bug fix, small feature): full loop. Bug fixes MUST start
  with a RED test reproducing the bug — the fix is not done until yesterday's
  bug is tomorrow's regression test.
- **Tier 3 — high stakes** (money, auth, data loss, concurrency, public API):
  start with a short **failure model**: list the ways this specific change can
  hurt (race condition, partial write, hostile input, overflow, unbounded
  growth, failed rollback…), and for each mode add a layer that can actually
  catch it — race/stress tests for concurrency, fuzzing for parsers, rollback
  rehearsal for migrations, benchmarks for latency budgets, API-compatibility
  checks for public libraries, contract tests for service boundaries,
  logging/metric assertions where silent production failure is a mode
  (full menu in `references/gauntlet.md`). Mutation and
  coverage cannot substitute for these; the generic gauntlet is the floor, not
  the ceiling. Then: full loop + property-based tests + mutation testing
  (tool-based if available) + adversarial pass — one explicit step trying to
  break your own implementation with hostile inputs before declaring done.
  Failure modes deliberately not covered go in EVIDENCE as known limits.
  The adversarial pass is you attacking your own work and shares your blind
  spots; where a spec gap would be expensive, consider independent
  verification below — a different kind of assurance, not another layer.

## Independent verification (Tier 3 option, experimental)

The gauntlet is evidence, not self-authentication: its checkers can be
unsound, its mappings can overclaim, and the spec can be incomplete. Human
spec approval mitigates only the last, by breaking author correlation, and
only before code exists — it does not make a spec complete.

Independent verification answers the rest where the stakes justify it: a
fresh-context agent that attacks the finished work before EVIDENCE is signed.
It reduces **task-context** correlation, not model correlation. **It is not a
gauntlet layer** — a layer is an executable check with a machine-evaluable
result; this is an agent returning prose a human must judge, spending the one
resource this skill otherwise guards. Experimental: the evidence is one case study
(`references/verifier-case-study.md` — for deciding whether to run this, not
for the verifier to read), not a benchmark.

**The protocol is `references/verifier.md`. Verification has not been performed
until that file has been read in full and executed; missing or unreadable →
`blocked`, never `passed`.** What cannot be traded away:

- **Fresh context, blind first**, four inputs only — the task contract, the
  approved SPEC, an exact source state, the entry point. Never your
  conversation. The draft EVIDENCE comes after its own results, not before.
- **It fixes nothing.** A SPEC gap goes to the human, never to the builder to
  self-amend.
- **The human grades the findings.** Behavioural findings are fixed and
  re-verified in a new context; description and mapping findings are fixed and
  disclosed without buying another round. Propose a grade if you like — the
  human decides any disputed or material one, and approves stopping at the
  cap. Self-grading is the obvious way to make this rule fail open.
- **Cap at two rounds**, more only by explicit approval. The cap does not limit
  the spending; it makes the spending someone's decision.
- **Verification is source-state-specific.** A state no verifier saw is
  `not performed`, whatever earlier rounds concluded. Fixing a behavioural
  finding after the final permitted round therefore ships an unverified state:
  record that as a declared downgrade and keep the earlier rounds as history.
- **Four states**: `passed` finalizes; `failed` and `blocked` do not;
  `not performed` finalizes only as a declared downgrade, like an unapproved
  spec. On Tier 3 it needs no apology — say so and claim less.

## Setup

**Isolation — do not mutate the user's working tree to do your work.** Declare
the mechanism in the SPEC, with one line of why: a worktree, a branch, or none —
the last only at Tier 1, where the blast radius is a typo. The human vetoes the
mechanism at approval rather than discovering it afterwards.

The trap: **a fresh worktree contains no gitignored content**, so the gauntlet
often cannot run there until dependencies are rebuilt. Two outcomes are
acceptable — rebuild and run there, or fall back to a branch and record why.
Never report green from a tree that never ran the suite.

Where the isolated tree and the tree the change lands in differ by ignored or
untracked content, say so in EVIDENCE: a green run in a tree missing the landing
tree's `.env` or build outputs is not evidence about the landing tree.

If the project has no test runner, no linter, or no type checking, set up the
minimal standard toolchain for the language **first** (see
`references/gauntlet.md`). A gauntlet can't run on bare ground. Setup changes
the user's environment — packages, config files, lockfiles — so it belongs in
the SPEC's setup plan, where spec approval authorizes it in one step; record
every environment change actually made in the evidence report. If the user
forbids adding tooling, fall back to manual layers (manual mutation, manual
execution) and record the reduced confidence honestly.

If the directory is not a git repository, propose `git init` in the SPEC's
setup plan. Version control is itself a gauntlet layer: commit at SPEC and at
each GREEN/REFACTOR checkpoint, so mutant restores are verifiable with
`git diff` (not by eyeball), a bad refactor is rolled back instead of debugged,
and the final diff shows exactly what changed. Checkpoint commits happen only
under that spec-approved authorization (or an explicit user request) — never
impose a commit cadence on a repo whose owner hasn't agreed to it. If the user
declines or git is unavailable, record that in EVIDENCE — mutant restores then
rest on rerunning the suite, a weaker guarantee — and identify the source state
with a tree hash instead of a SHA.
