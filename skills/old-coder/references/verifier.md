# VERIFY: fresh-context adversarial verification

The protocol for the "Independent verification" section of SKILL.md. Read it
in full before claiming verification was performed; the summary in SKILL.md is
not the protocol.

This is not a gauntlet layer and should not be run like one. A layer is an
executable check with a machine-evaluable result; this is an agent returning
prose a human has to grade. It exists because the gauntlet is necessary but
not self-authenticating: the spec may be incomplete, a checker may be unsound,
a mapping may overclaim, and EVIDENCE may not describe the state that shipped.
The attack order below goes after all four.

## Blind-phase inputs — exactly four

Give the verifier, before it sees anything else:

1. **The task contract.** The user's original request *plus every requirement,
   scope change and spec revision a human has explicitly approved since*. Not
   just the first message: without the approved changes, a legitimate scope
   revision reads as a spec gap and the verifier reports a false positive.
   Not the surrounding discussion either — no builder reasoning, defences,
   suggestions, or unapproved explanations.
2. **The approved SPEC.**
3. **The repository at an exact source state** (commit SHA, or a tree hash
   when git is absent).
4. **The gauntlet entry point.**

This protocol is instruction, not task evidence; the four-item limit applies
to task-specific inputs. The verifier is expected to know how to attack — it
is not expected to know anything about this task that the four items do not
carry.

Withhold the builder's conversation, the draft EVIDENCE, and the case study.
If a claim needs the builder's justification to stand, it is not proven.

The verifier reads the implementation freely — it is an attacker, not the
human whose review you are trying to make optional.

## Two phases

**Blind.** The verifier reproduces and attacks on its own and records: the
source state it observed, the numbers it got, its attack list, its initial
findings. **Then** it is shown the draft EVIDENCE and compares. The blind
record is append-only afterwards — comparison may add findings, never rewrite
what the blind pass saw. Without this the verifier is anchored to the
builder's framing and its fresh context is wasted.

## Attack order

Record what was tried at each surface, including the attacks that found
nothing. The attack list is the deliverable; findings are a bonus.

1. **The run.** Execute the entry point from the stated source state and
   record the result blind. Once the draft EVIDENCE is revealed, any mismatch
   suspends its claim until source state, environment, freshness and
   determinism have been reconciled — do not silently prefer either number.
   First confirm the environment actually tests the tree it claims to —
   a copied virtualenv, a stale install, or a cached artifact can silently
   exercise the original sources and make every later result meaningless.
2. **The spec against the contract.** The one failure class a test suite
   structurally cannot catch. What would a caller reasonably expect, given the
   stated deployment, that no scenario or Must NOT covers? Approved exclusions
   are not findings — but an approved exclusion *described inaccurately* is.
3. **The tests.** Try to make the suite pass wrongly: implementation keyed to
   test inputs, mocks swallowing the logic, assertions that cannot fail. Invent
   mutants the builder did not choose; the builder's mutant list encodes the
   builder's blind spots. Watch for tests that pin less than they claim — a
   boundary pinned in one function and not in its twin, a magnitude left free
   while its boundary is fixed, an assertion satisfied by a caller that never
   arrived.
4. **The checkers.** Feed every home-grown gate a known-bad input and confirm
   it fails. Then ask the harder question: does it cover the constraint it
   claims, or only one spelling of it?
5. **The mapping, both directions.** Every scenario, Must NOT and
   failure-model row must name a falsification procedure that can be made to
   fail. Also look the other way: tests with no scenario, and demonstrated
   failure modes with no row.

**Before reporting any surviving mutant, prove it diverges.** Construct a
concrete input where mutant and original disagree. A survivor you cannot make
disagree is an equivalent mutant, and reporting it as a defect sends the
builder to write a test that asserts non-behavior.

## The verifier fails closed too

- "Looks good" is not a verdict.
- It fixes nothing. Findings return through the normal loop. A **SPEC gap goes
  to the human**, never to the builder to self-amend. An EVIDENCE number that
  disagrees with the rerun is a report defect: fix the report, then a full
  fresh run.
- If it cannot complete verification — missing tool, no fresh context
  available, this file unreadable — that is `blocked`, not a skip.
- **Optional canary.** Run it once against a build with a planted defect and
  watch it catch it. Plant in an isolated copy, never in the candidate; the
  verifier must not know the defect's location or kind; a missed canary voids
  that verdict. A caught canary is a floor, not a capability proof: it shows
  the verifier can reject one obvious error, nothing about coverage.

## Grading findings — the rule that makes this terminate

| Finding | Response |
|---|---|
| **Behavioural**: the code does the wrong thing, or a gate cannot fail | fix, then re-verify in a **new** verifier context |
| **Description / mapping**: the spec, a comment or EVIDENCE says something untrue about code that is correct | fix and disclose; **no new round** |

**The human grades, not the builder.** The builder may propose a grade; the
human decides any material or disputed one and approves stopping at the cap.
Left to self-grading this rule fails open in the obvious way — call a boundary
defect a documentation defect and the round is avoided. It matters most when
the finding touches the SPEC, where the question is precisely whether the
document is wrong about correct code, or whether it has exposed a behavioural
requirement nobody wrote down. That is the human's call by the same rule that
sends SPEC gaps to the human in the first place.

Without this split, "fix every finding" times "start a new verifier after any
change" is a loop that terminates only when a round returns the empty set.
Prose has no such fixpoint.

**Be clear about the trade.** Grading buys termination by giving up
completeness. A behavioural gap can live inside a round you chose not to run,
and that is not hypothetical — it has happened at least once, in the run
written up in `verifier-case-study.md`. The price is worth paying because the
alternative is a process with no stopping condition at all. Say in EVIDENCE
which rounds were not run.

Cap at two rounds by default. More needs explicit human approval, recorded.
The cap does not stop the spending; it makes the spending someone's decision,
which is the part that was missing when this protocol was first drafted.

## Verification is source-state-specific

A verdict attaches to the state that was verified, not to the project. A state
no verifier has seen is `not performed`, however many rounds preceded it and
whatever they concluded.

This bites at exactly one place: a behavioural finding fixed after the final
permitted round. The fix is correct and the round cap is correct, and the
shipped state is still unverified. Do not launder that by inheriting the
previous verdict, and do not invent a fifth state for it. Record the final
state as `not performed` — a declared downgrade — and keep the earlier rounds
as history:

```text
Independent verification: not performed against final source state <SHA>.
<n> earlier rounds were performed; the last verified state <SHA> returned
<verdict>, and the fixes made since are disclosed below as unverified.
```

## Four states, recorded in EVIDENCE

| State | May EVIDENCE be finalized? |
|---|---|
| `passed` | yes |
| `failed` | no |
| `blocked` — verification could not be completed | no |
| `not performed` | only as a declared downgrade, with the reason, exactly like an unapproved spec |

EVIDENCE records the verdict, the verifier's host and model family, whether
the context was fresh, which inputs it received, the attack list, each finding
and its resolution, and any canary. When findings were fixed **after** the
last verified state, say which — they are not independently verified.

## Report template

```markdown
### Independent verification
- Verifier: <host / model family>; fresh context; given repo @ <state> + task
  contract + SPEC + entry point. Not given the builder's conversation.
  Correlation broken: task context. Not broken: model.
- Rounds: <n> (cap <m>). Round <k> verdict: <passed|failed|blocked>.
- Attacked: <run | spec vs contract | test-gaming | checker coverage | mapping>
  — what was tried, not only what was found.
- Findings: <behavioural: ... → fix + round n+1> / <description: ... → fixed,
  disclosed> (or "none survived the attacks listed above")
- Canary: <planted defect → caught | MISSED, verdict void | not run>
- Fixed after the last verified state, therefore unverified: <list | none>
```
