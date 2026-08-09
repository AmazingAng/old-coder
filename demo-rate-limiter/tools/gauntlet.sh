#!/bin/sh
# Gauntlet entry point: run every layer; fail on the first broken one.
set -e
cd "$(dirname "$0")/.."
rm -f .coverage coverage.xml   # stale artifacts from previous runs
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
# sleep`. Deliberately not `[[:<:]]time`, which would fire on conftest's own
# "No real time in tests" docstring and on test_non_monotonic_clock_* — the
# fix belongs in the pattern, never in an exclusion.
must_not_match 'import[[:space:]]+time|from[[:space:]]+time[[:space:]]+import|time\.|datetime|sleep[[:space:]]*\(|perf_counter[[:space:]]*\(|monotonic[[:space:]]*\(' tests
# Bracketed letters stop the pattern literal from matching itself.
must_not_match 'api[_-]?key|s[e]cret|pass[w]ord|t[o]ken|private[_-]?key' src tests tools examples
echo "must-not scans clean"
echo "=== mutation ==="
"$PY/python" tools/mutants.py
echo "=== real execution ==="
"$PY/python" examples/demo.py
echo "=== gauntlet: all layers green ==="
