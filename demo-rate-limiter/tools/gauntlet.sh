#!/bin/sh
# Gauntlet entry point: run every layer; fail on the first broken one.
set -e
cd "$(dirname "$0")/.."
rm -f .coverage coverage.xml   # stale artifacts from previous runs
PY=.venv/bin

# Must-find-nothing grep, fail closed: rc 1 (no matches) is the only pass;
# rc 0 = forbidden pattern present, rc >= 2 = the check itself broke.
must_not_match() {
  pattern=$1; shift
  if grep -rniE "$pattern" "$@"; then
    echo "FAIL: forbidden pattern present: $pattern"; return 1
  elif [ $? -ne 1 ]; then
    echo "FAIL: scan itself broke (fail closed): $pattern"; return 1
  fi
}

echo "=== tests + coverage ==="
"$PY/pytest" -q --cov=ratelimiter --cov-report=term-missing
echo "=== types ==="
"$PY/mypy" src tests examples tools
echo "=== lint + format ==="
"$PY/ruff" check .
"$PY/ruff" format --check .
echo "=== supply chain ==="
"$PY/pip-audit" -r requirements-dev.txt
echo "=== must-not scans ==="
must_not_match 'time\.' tests
# Bracketed letters stop the pattern literal from matching itself.
must_not_match 'api[_-]?key|s[e]cret|pass[w]ord|t[o]ken|private[_-]?key' src tests tools examples
echo "must-not scans clean"
echo "=== mutation ==="
"$PY/python" tools/mutants.py
echo "=== real execution ==="
"$PY/python" examples/demo.py
echo "=== gauntlet: all layers green ==="
