# Contributing

Thanks for considering it. This repo is small and opinionated, so it is worth
saying up front what gets merged quickly and what gets a long conversation.

## What this repo is, and why review is unusual here

`skills/old-coder/` is not documentation about code. **It is instructions that
coding agents will obey.** A pull request that changes one line of `SKILL.md`
changes what every agent loading this skill does next, on every repo it touches.

So the review question is never "is this sentence true?" — it is **"what will an
agent do differently after this merges?"** Expect reviewers to read your diff
that way, and expect a security-shaped read of any change that touches
approvals, permissions, what gets executed, or what gets written outside the
repo.

## The bar

**A rule earns its place if its absence would let someone believe something
false.** Not if its presence would be nice to have. That applies to rules in
`SKILL.md`, fields in the EVIDENCE template, and layers in the gauntlet alike.

The best contributions so far have all had the same shape: *here is a specific
way the skill fails, here is the run where I hit it, here is the smallest rule
that closes it.* An observed failure is worth more than a plausible one.

**Say what you left out.** If your fork does something more opinionated than
what you are proposing, say so and leave it out of the PR. Two of the most
useful PRs here did exactly that.

## Adding a gauntlet layer

A new layer has to pass three tests:

1. **Orthogonal** — it catches a failure class no existing layer catches.
2. **Can fail meaningfully** — you have watched it fail on a known-bad input.
   A layer nobody has seen fail is not a layer.
3. **Tool-ready** — a real command exists in the common ecosystems, or you have
   written the manual procedure.

Layers are cheap to propose and expensive to keep. Expect the second test to be
where most proposals stop.

## The failure mode we care about most

Read the note at the top of `SKILL.md` about mechanisms that report success
while doing nothing. This project has hit that five times — a coverage layer
that printed a percentage and exited 0, a gate that failed closed perfectly
while guarding a spelling, a mutation runner scoring a mutant it never
executed, an approval that was an answer to a different question, a green suite
reported from a tree that could not run it.

If your change adds anything that produces a claim, say in the PR what it does
when it is broken. If the answer is "reports success", it is not finished.

## Keeping `SKILL.md` short

The main file is loaded in full on every invocation, including for tasks that
will never use the rule you are adding. Detail belongs in `references/`, behind
a pointer.

**In one, out one.** If you add to `SKILL.md`, look for something that can move
to a reference or come out entirely. A file long enough to be skimmed is its
own fail-open: nothing tells you which rule the agent missed.

## Changing the demo

`demo-rate-limiter/` is the worked example, and changes to it go through the
loop the skill describes — spec revision first, RED test watched failing,
minimal implementation, full gauntlet, then `evidence.md` rebound to the new
commit with `tools/source_state.sh`. A demo change that skips the loop is not
a demo of the loop.

Run `./tools/gauntlet.sh` before opening the PR. It must exit 0.

## Practical notes

- Drafts are welcome, and a series of small independent PRs beats one large
  one. Say which PRs depend on which.
- CI runs on pull requests, but a first contribution from a fork needs a
  maintainer to approve the workflow run. That is normal; it is not stuck.
- Both `README.md` and `README-zh.md` exist. Updating only one is fine — say so
  in the PR and someone will follow up.
- Issues that describe a failure you actually hit are always welcome, even
  without a fix attached. The failure is the valuable part.
