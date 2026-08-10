# Case study: six rounds against an already-green gauntlet

**Do not load this while running the protocol.** It names the defect classes
one codebase turned out to have, and an attacker primed with that list looks
there first and elsewhere second. It is here for someone deciding *whether*
to run verification and what it costs — not for the verifier.

Six rounds against a 99-line Python rate limiter that was already passing ten
gauntlet layers, 100% branch coverage and 8/8 mutation, with a
multiply-rebound evidence report. Same model as the builder throughout, so
this measures reproducibility, not model independence. Roughly 550k tokens.

- **Rounds 1–3 found five behavioural defects** nothing in the gauntlet could
  reach: an unbounded key map usable as a remote memory-exhaustion attack
  against the component meant to prevent one; `limit=NaN` producing a limiter
  that always allowed; 2× over-allow under threads; a lock that covered
  check-and-append but not the clock read; and — the most transferable one —
  a mutation runner reporting kills for mutants it never executed, because
  two same-size mutants written in the same second shared a bytecode cache.
  That last defect could only ever inflate the score, so it could never
  surface as a red gauntlet.
- **Rounds 4–6 found one behavioural gap and a stream of prose inaccuracies**,
  two of which were introduced by the round that fixed the previous one. That
  is why a single clean round does not mean converged, and why the grading
  rule above exists. The marginal round was clearly negative by round 5.
- **An A/B design failed.** Planting a defect in one copy and verifying a
  clean copy as a false-positive control did not work: the "clean" copy was
  not clean — it independently invented the planted mutation and correctly
  reported it. No false-positive rate could be measured. The two false
  positives that did occur were both caused by feeding the verifier a
  subdirectory instead of the repository, and a tree polluted by an editable
  install. **Verifier noise tracked input quality.**
- **Verification's late-stage output is not bugs.** It is the discovery that
  SPEC and EVIDENCE are describing code that does something else — which
  matters precisely because those two documents are the only things the human
  reads.
