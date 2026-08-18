#!/bin/sh
# Gauntlet entry point: run every layer; fail on the first broken one.
set -e
cd "$(dirname "$0")/.."
rm -f .coverage coverage.xml   # stale artifacts from previous runs
# Bytecode caches are both a correctness hazard for the mutation layer and
# binary noise the must-not scans would grep through.
find . -name __pycache__ -type d -prune -exec rm -rf {} +
PY=.venv/bin

. tools/must_not_match.sh
. tools/gauntlet_layers.sh

run_layer orchestration-self-test sh tools/test_gauntlet_orchestration.sh

run_layer checker-self-test sh tools/test_gauntlet_checks.sh

run_layer source-state-self-test "$PY/pytest" -q tests/test_source_state.py

# --cov-fail-under makes this layer a gate. Without it the layer printed a
# percentage and exited 0 no matter how far coverage fell: a fail-open layer
# inside a gauntlet whose first line promises to fail on the first broken one.
run_layer tests-coverage \
  "$PY/pytest" -q --cov=ratelimiter --cov-report=term-missing --cov-fail-under=100

run_layer types "$PY/mypy" src tests examples tools

layer_lint_format() {
  "$PY/ruff" check . || return $?
  "$PY/ruff" format --check . || return $?
}
run_layer lint-format layer_lint_format

run_layer supply-chain "$PY/pip-audit" -r requirements-dev.txt

layer_must_not_scans() {
# Matches usage forms, not the word: `time\.` alone missed `from time import
# sleep`. Deliberately not a bare word-boundary match on `time`, which fires
# on conftest's own "No real time in tests" docstring, on `timestamps`, on
# `timeout=` and on ordinary prose — the fix belongs in the pattern, never in
# an exclusion.
#
# Scope is narrower than the Must NOT's ambition: `Event.wait(timeout=)` and
# `Thread.join(timeout=)` are NOT matched. They are declared in spec.md as an
# exception rather than excluded here, because a pattern cannot decide intent.
  must_not_match 'import[[:space:]]+time|from[[:space:]]+time[[:space:]]+import|time\.[a-zA-Z_]|datetime|sleep[[:space:]]*\(|perf_counter[[:space:]]*\(|monotonic[[:space:]]*\(' tests || return $?
# Bracketed letters stop the pattern literal from matching itself. The path
# list now includes CI config and metadata: workflows are where credentials
# actually appear, and scanning only src/tests/tools/examples missed them.
  must_not_match 'api[_-]?key|s[e]cret|pass[w]ord|t[o]ken|private[_ -]?key|BEGIN[[:space:]]+[A-Z ]*PRIVATE' \
    src tests tools examples spec.md pyproject.toml requirements-dev.txt ../.github || return $?
  echo "must-not scans clean"
}
run_layer must-not-scans layer_must_not_scans

# Negative control first: a killer and a strictly-equivalent mutant of
# identical size under one pinned mtime. If bytecode ever leaks between runs,
# the equivalent one inherits the killer's verdict and the whole kill count is
# inflated — silently, and only ever upward.
run_layer mutation-control "$PY/python" tools/mutants.py --negative-control
run_layer mutation "$PY/python" tools/mutants.py

run_layer real-execution "$PY/python" examples/demo.py

run_layer source-state tools/source_state.sh

finish_gauntlet
