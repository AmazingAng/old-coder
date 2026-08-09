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

echo "=== checker self-test ==="
sh tools/test_gauntlet_checks.sh

echo "=== tests + coverage ==="
# --cov-fail-under makes this layer a gate. Without it the layer printed a
# percentage and exited 0 no matter how far coverage fell: a fail-open layer
# inside a gauntlet whose first line promises to fail on the first broken one.
"$PY/pytest" -q --cov=ratelimiter --cov-report=term-missing --cov-fail-under=100
echo "=== types ==="
"$PY/mypy" src tests examples tools
echo "=== lint + format ==="
"$PY/ruff" check .
"$PY/ruff" format --check .
echo "=== supply chain ==="
"$PY/pip-audit" -r requirements-dev.txt
echo "=== must-not scans ==="
# Matches usage forms, not the word: `time\.` alone missed `from time import
# sleep`. Deliberately not `[[:<:]]time`, which fires on conftest's own "No
# real time in tests" docstring, on `timestamps`, on `timeout=` and on prose
# like "hold time constant" — the fix belongs in the pattern, never in an
# exclusion. (An earlier version of this comment also claimed it would fire on
# test_non_monotonic_clock_*; that was invented — the name has no "time" in
# it at all.)
#
# Scope is deliberately narrower than the Must NOT's ambition: it catches real
# time being read or slept on, not every way a test could depend on wall
# clock. `Event.wait(timeout=)` and `Thread.join(timeout=)` are NOT matched —
# they are deadlock guards in the concurrency tests, declared as an exception
# in spec.md rather than excluded here. A pattern cannot decide intent, so the
# spec says what the gate actually covers instead of claiming more.
must_not_match 'import[[:space:]]+time|from[[:space:]]+time[[:space:]]+import|time\.[a-zA-Z_]|datetime|sleep[[:space:]]*\(|perf_counter[[:space:]]*\(|monotonic[[:space:]]*\(' tests
# Bracketed letters stop the pattern literal from matching itself. The path
# list now includes CI config and metadata: workflows are where credentials
# actually appear, and scanning only src/tests/tools/examples missed them.
must_not_match 'api[_-]?key|s[e]cret|pass[w]ord|t[o]ken|private[_ -]?key|BEGIN[[:space:]]+[A-Z ]*PRIVATE' \
  src tests tools examples spec.md pyproject.toml requirements-dev.txt ../.github
echo "must-not scans clean"
echo "=== mutation ==="
# Negative control first: a killer and a strictly-equivalent mutant of
# identical size under one pinned mtime. If bytecode ever leaks between runs,
# the equivalent one inherits the killer's verdict and the whole kill count is
# inflated — silently, and only ever upward.
"$PY/python" tools/mutants.py --negative-control
"$PY/python" tools/mutants.py
echo "=== real execution ==="
"$PY/python" examples/demo.py
echo "=== gauntlet: all layers green ==="
