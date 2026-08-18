# Gauntlet Tooling by Ecosystem

Prefer whatever the project already uses (check package.json / pyproject.toml /
Makefile / CI config first). These are the defaults when nothing exists.

## Python

| Layer | Tool | Command |
|---|---|---|
| Tests | pytest | `pytest -q` |
| Types | mypy | `mypy <pkg>` (or pyright) |
| Lint + format | ruff | `ruff check . && ruff format --check .` |
| Changed-line coverage | coverage.py | `pytest --cov=<pkg> --cov-branch --cov-report=term-missing --cov-fail-under=<n>` — without the threshold flag the layer prints a number and exits 0, so it can never fail; `diff-cover coverage.xml --fail-under=100` gates changed lines specifically |
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

## Java

| Layer | Tool | Command |
|---|---|---|
| Tests | JUnit 5 via Maven / Gradle | `./mvnw test` / `./gradlew test` |
| Types | javac via Maven / Gradle | `./mvnw compile` / `./gradlew classes` |
| Lint + format | Checkstyle + Spotless | `./mvnw checkstyle:check spotless:check` / `./gradlew check spotlessCheck` |
| Changed-line coverage | JaCoCo | `./mvnw verify` / `./gradlew test jacocoTestReport`, then inspect the XML/HTML report for touched lines and branches |
| Mutation | PIT | `./mvnw test-compile org.pitest:pitest-maven:mutationCoverage` / `./gradlew pitest`; scope changed packages or classes |
| Property-based | jqwik | write `@Property` tests; the normal JUnit test command runs them |

## Scala

| Layer | Tool | Command |
|---|---|---|
| Tests | MUnit / ScalaTest via sbt | `sbt test` |
| Types | Scala compiler | `sbt "compile" "Test / compile"` |
| Lint + format | Scalafix + Scalafmt | `sbt scalafmtCheckAll "scalafixAll --check"` |
| Changed-line coverage | scoverage | `sbt clean coverage test coverageReport`, then inspect the report for touched statements and branches |
| Mutation | Stryker4s | `sbt stryker`; scope `mutate` to changed source files when the full project is slow |
| Property-based | ScalaCheck | define `Properties` or framework-integrated properties; `sbt test` runs them |

## SQL

SQL has no portable test runner or type checker. Configure the actual dialect,
use the project's migration/query framework, and validate against a disposable
instance of the same database engine used in production.

| Layer | Tool | Command |
|---|---|---|
| Tests | project/database-native tests | run the project's test command (`dbt test` for dbt), including migrations, constraints, and result-set assertions |
| Parse + schema checks | SQLFluff + target database | `sqlfluff parse --dialect <dialect> <changed.sql>`, then prepare, explain, or execute each changed statement against the disposable database |
| Lint + format | SQLFluff | `sqlfluff lint --dialect <dialect> .`; apply rule fixes with `sqlfluff fix` (`sqlfluff format` handles layout only) |
| Changed-statement coverage | spec-to-test mapping | map every changed statement, predicate branch, constraint, and migration direction to an integration test; record any unexercised item |
| Mutation | manual | use the manual procedure below to alter predicates, joins, aggregates, constraints, and migration steps; every mutant must fail a test |
| Property-based | host-language generator + target database | generate rows and assert schema, query, and round-trip invariants through the project test runner |

## Emacs Lisp

| Layer | Tool | Command |
|---|---|---|
| Tests | ERT | `emacs -Q --batch -L . -l ert -l <test-file> -f ert-run-tests-batch-and-exit` |
| Compile checks | byte compiler | `emacs -Q --batch -L . --eval '(setq byte-compile-error-on-warn t)' -f batch-byte-compile <files>` |
| Lint | package-lint + checkdoc | run `package-lint-batch-and-exit` and `checkdoc` in batch mode over every changed `.el` file |
| Changed-form coverage | testcover / undercover.el | instrument changed files in the batch ERT runner and verify every touched form is exercised |
| Mutation | no mature default | use the manual mutation procedure below on changed defuns and run the ERT suite for each mutant |
| Property-based | deterministic ERT generators | generate inputs in an `ert-deftest`, pin the random seed, and assert invariants |

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

**Reach for the project's mutation tool first.** A real tool generates mutants
from the syntax tree, so it cannot apply a mutant to code that has moved and it
cannot report a mutant it did not run. A hand-written mutant list matched
against source text is a second copy of the code: it goes stale on every
refactor of the thing it guards, and it fails in the one direction no gauntlet
can catch. Use the procedure below when no tool exists for the language, not as
a default.

**A hand-rolled runner must prove it executed each mutant.** This is the sharp
edge, and this repo's own demo found it: two same-size mutants written in the
same second shared a bytecode cache, so the runner reported kills for mutants it
never executed. That class of defect can *only* inflate the score, which means
it can never surface as a red gauntlet — the layer stays green precisely because
it is broken. `tools/mutants.py` now guards against it (mtime pinning, a cache
check that aborts the run); any runner written from this procedure needs the
equivalent, and EVIDENCE should say which check proves execution.

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

Gate code itself must fail closed (see the checker note in SKILL.md): `set -e`
at the top, no `|| true`, no `2>/dev/null`, and spell out the exit-code cases
of any command whose codes are ambiguous. The classic trap is a
must-find-nothing grep: rc 1 (no matches) is the only pass; rc 0 means the
forbidden pattern exists, and rc ≥ 2 means the check itself broke (unreadable
input, bad pattern) — both must fail the layer, or an unreadable file turns
into a vacuous pass. Prove each home-grown check can fail with a one-off
negative control (feed it a known-bad fixture; make its input unreadable) and
record the control in EVIDENCE's honest notes.

Keep the assurance boundary explicit: application coverage and mutation target
the subject under test; do not widen them across every orchestration script by
default. Protect home-grown tools in the gauntlet's trust chain with targeted
negative controls for identified fail-open modes, and pin the failure reason,
not merely a non-zero status. A control proves only its named known-bad case,
not the whole tool. For the entry point itself, bind execution to completion:
maintain a fixed expected-layer manifest, record each layer only after its
commands succeed, and audit the manifest before printing success. Do not use a
heading as evidence that a layer ran, and do not rely on `set -e` through `&&`
or another conditional context; handle the command status explicitly.

## Templates

The Gherkin scenario template, the SPEC template, and the EVIDENCE report
template live in `references/templates.md`. This file is read while building
the gauntlet; that one is read while writing the two artifacts the human
reads.
