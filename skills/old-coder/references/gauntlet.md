# Gauntlet Tooling by Ecosystem

Prefer whatever the project already uses (check package.json / pyproject.toml /
Makefile / CI config first). These are the defaults when nothing exists.

## Python

| Layer | Tool | Command |
|---|---|---|
| Tests | pytest | `pytest -q` |
| Types | mypy | `mypy <pkg>` (or pyright) |
| Lint + format | ruff | `ruff check . && ruff format --check .` |
| Changed-line coverage | coverage.py | `pytest --cov=<pkg> --cov-branch --cov-report=term-missing` then verify the lines you touched appear covered; `diff-cover coverage.xml` automates changed-line % against git |
| Mutation | mutmut (3+) | configure `[tool.mutmut] source_paths = ["src/"]` in pyproject.toml, then `mutmut run` (target one module with `mutmut run "my_module*"`); survivors = weak tests |
| Property-based | hypothesis | `@given(...)` strategies for invariants |

## JavaScript / TypeScript

| Layer | Tool | Command |
|---|---|---|
| Tests | vitest / jest | `npx vitest run` / `npx jest` |
| Types | tsc | `npx tsc --noEmit` |
| Lint | eslint | `npx eslint .` |
| Changed-line coverage | vitest/jest coverage | `npx vitest run --coverage` (v8, per-file report); check touched files |
| Mutation | Stryker | `npx stryker run` (scope with `mutate: [<changed files>]` — full-project runs are slow) |
| Property-based | fast-check | `fc.assert(fc.property(...))` |

## Go

| Layer | Tool | Command |
|---|---|---|
| Tests | go test | `go test ./... -race` |
| Types | compiler | `go build ./...` |
| Lint | go vet + staticcheck | `go vet ./... && staticcheck ./...` |
| Coverage | built-in | `go test -coverprofile=c.out ./... && go tool cover -func=c.out` |
| Mutation | (no mature default) | manual mutation |
| Property-based | testing/quick or rapid | `rapid.Check(t, ...)` |

## Rust

| Layer | Tool | Command |
|---|---|---|
| Tests | cargo | `cargo test` |
| Types | compiler | `cargo check` |
| Lint | clippy | `cargo clippy -- -D warnings` |
| Coverage | llvm-cov | `cargo llvm-cov --branch` |
| Mutation | cargo-mutants | `cargo mutants --file <changed file>` |
| Property-based | proptest | `proptest!` macros |

## Extended layer menu (any ecosystem)

Always-on layers live in SKILL.md's table; these are picked per task by the
Tier 3 failure model (or when the domain plainly calls for them).

| Layer | Tools | When |
|---|---|---|
| Dependency audit | pip-audit / npm audit / govulncheck / cargo-audit | whenever the dependency set changed |
| License check | pip-licenses / license-checker / go-licenses / cargo-license | when adding deps to redistributable code |
| Secret scan | gitleaks (language-agnostic) | on the diff before committing |
| Capability diff | manual diff review, or semgrep rules | always cheap: did the change start using network / subprocess / filesystem / env vars it didn't before? An agent-added capability nobody asked for is a red flag |
| Suite health | pytest-randomly (py) / `vitest --sequence.shuffle` (ts) / `go test -shuffle=on` / `cargo test -- --shuffle` (nightly) | randomized order per run; repeat suspected flakes |
| API compatibility | griffe (py) / api-extractor (ts) / apidiff (go) / cargo-semver-checks (rust) | when a public API is touched |
| Concurrency | `go test -race` / ThreadSanitizer (C/C++/Rust) / loom (rust) / threading stress + rerun (py) | Tier 3, when the failure model names races |
| Performance | pytest-benchmark / hyperfine / criterion | only when the spec states a budget |
| UI checks | axe-core (accessibility) / Playwright screenshot diff (visual regression) / Lighthouse (perf & a11y budgets) | when the change touches user-facing UI — backend layers say nothing about a broken layout or an unreadable contrast |
| Version matrix | tox / nox / CI matrix | when the project claims support for multiple language or platform versions — one version green is not evidence for the others |
| Observability | assert critical paths emit logs/metrics (capture in tests or grep) | when the failure model includes "fails silently in production" — passing all tests but breaking invisibly is still a failure |

New dependencies are a SPEC matter first, a tool matter second: each one needs
a one-line justification in the setup plan, and EVIDENCE records the final
dependency diff so the human can see exactly what the agent pulled in.

## Manual mutation procedure (any language, no tool)

Script this rather than hand-editing, and **persist the script in the repo**
(e.g. `tools/mutants.py`): it holds the original source, applies each mutant by
unique string replacement, runs the suite, and restores. Hand-editing N times
invites restore mistakes, and the EVIDENCE rule (all numbers from one final
fresh run) means you will run the mutants at least twice — a persisted script
makes the rerun free, the mutant list auditable, and the reported score
re-runnable by the human, which a scratch-directory script is not.

1. Pick the new/changed implementation code.
2. One at a time, introduce 3–5 plausible bugs, biased toward the logic that
   matters most:
   - flip a comparison (`<` → `<=`, `==` → `!=`)
   - off-by-one a loop bound or slice index
   - delete one branch of a conditional / remove an early return
   - swap `and`/`or`; negate a boolean
   - replace a returned value with a constant (`0`, `null`, `""`)
3. Run the test suite after each mutant. **Every mutant must make at least one
   test fail.** A surviving mutant means a missing or vacuous assertion — add
   the test that kills it, then continue.
4. Restore the original code (verify with `git diff` that only intended changes
   remain) and run the suite once more to confirm green.
5. Report as: "manual mutation: N/N killed".

## Gauntlet entry point

Persist one command that runs every layer in sequence and fails on the first
broken one (e.g. `tools/gauntlet.sh`: tests+coverage → types → lint → mutation
→ real execution). Start the script by deleting stale artifacts from previous
runs (old coverage data, report files) so no layer can accidentally read a
prior run's output — freshness by mechanism, not discipline. (Keep tool
databases that accumulate value, e.g. hypothesis's example store.) The "final
fresh run" IS this command; EVIDENCE cites it, and the human can rerun the
whole report with it. Pin dev-tool versions
(requirements-dev.txt, package.json devDependencies with exact versions, etc.)
so the rerun uses the same gauntlet.

## Gherkin scenario template (for the SPEC step)

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
  in prose is working-directory-sensitive and will fail to reproduce
- Toolchain: <pinned versions file, e.g. requirements-dev.txt>
- Entry point: <single command that reruns every layer>

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

### Skipped layers
- <layer>: <reason>  (or "none")

### Honest notes
- <failures hit during the task and how they were resolved; spec revisions; anything reducing confidence>
```

