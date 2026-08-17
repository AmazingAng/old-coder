# SPEC and EVIDENCE Templates

The fill-in forms for the two artifacts the human actually reads. The layers
they reference are defined in `gauntlet.md`.

## SPEC template (for the SPEC step)

Written before any implementation file is touched.

```markdown
# SPEC — <task name>

- Tier: <1|2|3>
- Setup plan:
  - Tools to install: <or "none">
  - Git: <init? checkpoint commit cadence? commit flags the repo mandates>
  - Files the gauntlet will add, **by path**: `tools/mutants.py` (mutation
    layer), `tools/gauntlet.sh` (entry point) — mark either "already exists,
    reused" — plus any fixture or harness file
  - New dependencies: <each with a one-line justification, or "none">

## Scenarios
<Gherkin below>

## Must NOT
- <negative constraint / invariant that must survive>

## Revisions
- <appended only; each entry says what changed and why>
```

`## Revisions` is where "the spec is append-only, revise it visibly" stops being
a promise. Without somewhere to write the revision, a spec that changed
mid-task and a spec that never changed are the same document, and a reader
cannot tell which one they are holding.

**If the human rejects the spec**, revise `SPEC.md` in place, add the reason to
`## Revisions`, and re-request approval. Do not delete it and start clean —
what the human turned down, and why, is the most useful thing in the file.

### Gherkin scenario template

```gherkin
Feature: <capability in user language>
  Scenario: <one concrete behavior>
    Given <concrete starting state>
    When  <concrete action with concrete input>
    Then  <concrete observable outcome, exact values>

  Scenario: <the error case>
    Given ...
    When  <invalid/hostile input>
    Then  <exact error type/message/status, and what state must NOT change>
```

Each scenario maps 1:1 to at least one automated test; name the test after the
scenario so the evidence report's spec→test mapping is mechanical.

## Evidence report template (for the EVIDENCE step)

```markdown
## Evidence Report — <task name> (Tier <1|2|3>)

- Spec approval: <obtained from user | not obtained (autonomous run) —
  confidence downgraded; spec is the artifact to review after the fact>
- Source state: <commit SHA | no git: sha256 tree hash> — persist the
  computation as a script (e.g. tools/source_state.sh); a hash recipe written
  in prose is working-directory-sensitive and will fail to reproduce. When
  Git exists, derive the tree hash from version-controlled inputs, fail on
  relevant staged, unstaged, deleted, or non-ignored untracked files, and
  never hash ambient ignored build artifacts
- Toolchain: <pinned versions file, e.g. requirements-dev.txt>
- Entry point: <single command that reruns every layer>
- Independent verification: <not performed | passed | failed | blocked>
  **against the final source state** — a state no verifier saw is
  `not performed` however many rounds preceded it (Tier 3; protocol in
  `verifier.md`)

### Spec → Test mapping
Status is one of: **pass / fail / unverified / n-a**. A row mapped to
"skipped: <reason>" must carry unverified or n-a — never pass.

| Scenario | Test | Status |
|---|---|---|
| <scenario name> | <test file>::<test name> | pass |
| Must NOT: <negative constraint> | <test / layer / skipped: reason> | pass \| unverified |

### Gauntlet (final fresh run)
| Layer | Command | Result |
|---|---|---|
| Tests | <cmd> | <N> passed, 0 failed |
| Types | <cmd> | 0 errors |
| Lint | <cmd> | 0 warnings |
| Changed-line coverage | <cmd> | <covered>/<total> changed lines (list any misses) |
| Mutation | <tool or "manual"> | <killed>/<total> killed |
| Property-based | <cmd> | <N> properties, <examples/property> examples each |
| Real execution | <cmd> | <observed output> |
| Supply chain | <cmd> | 0 known vulns; new deps: none (or list, each ↔ SPEC justification) |
| Suite health | <cmd> | randomized order (seed <n>), all passed |

### Independent verification (never omit; see verifier.md)
- Verifier: <host / model family>; fresh context; which inputs it received;
  what correlation that breaks and what it does not.
- Rounds: <n> (cap <m>); verdict per round, each against the state it saw.
- Grading: who classified each finding behavioural vs description, and who
  approved stopping.
- Attacked: <what was tried, not only what was found>.
- Findings: behavioural (fixed, then re-verified in a new context) vs
  description/mapping (fixed and disclosed, no new round).
- Fixed after the last verified state, therefore unverified: <list | none>.

### Layers not run as specified
Split by status, because they mean different things to a reader:
- **N-A (this project has no such surface):** <layer — why it does not exist here>
- **UNAVAILABLE (tool missing):** <layer — which tool, nothing run in its place>
- **SUBSTITUTED:** <layer — what ran instead, and what that cannot detect>
- (or "none")

### Dismissed review findings
Fixes are self-evidencing; dismissals are not. One line each:
- <finding> — dismissed because <the command / file:line / test that disproves
  it>. <If the argument is "no alternative exists": which call sites it covers,
  and which it does not.>
- (or "none — every finding was fixed or accepted as a known limit")

### Structural blind spot
- <the layer this project cannot run at all, e.g. "the suite never exercises the
  container runtime, so nothing here is evidence about deployment behavior">

### Honest notes
- <failures hit during the task and how they were resolved; spec revisions; anything reducing confidence>
```

**Why "layers not run" is split three ways.** One "skipped" list collapses
three states a reader has to tell apart: there is no such surface in this
project, versus the surface exists but the tool was missing and nothing ran,
versus something else ran and here is what it cannot detect. Those are very
different confidence claims and they read identically as "skipped". The third
is the dangerous one: `SUBSTITUTED` may never be written as a pass. Two repeat
runs in place of randomized order is not "suite health: stable" — it is
`SUBSTITUTED (2 repeat runs — cannot detect whole-suite order dependence)`. A
reader who cannot tell a substitute from the real layer reads "found nothing"
where the truth is "did not look with that instrument". `N-A` is not a
degraded run at all: three `N-A` layers describe the project, and EVIDENCE
should say so rather than leaving a reader to count absences.

**Why dismissals need a line each.** A fix carries its own evidence — the test
that now passes. A dismissal carries none: "not a real problem" is
indistinguishable from "did not check". Naming the command, `file:line`, or
test that disproves the finding is the same rule the verification protocol
already applies to attack lists — say what you tried, not only what you found.

**Why name the blind spot.** A layer a project cannot run at all otherwise
reads as absent rather than accepted. Stating it converts a silent gap into a
known limit the reader can price in.
