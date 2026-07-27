#!/bin/sh
# Gauntlet entry point: run every layer; fail on the first broken one.
set -e
cd "$(dirname "$0")/.."
PY=.venv/bin

echo "=== tests + coverage ==="
"$PY/pytest" -q --cov=ratelimiter --cov-report=term-missing
echo "=== types ==="
"$PY/mypy" src tests examples tools
echo "=== lint + format ==="
"$PY/ruff" check .
"$PY/ruff" format --check .
echo "=== mutation ==="
"$PY/python" tools/mutants.py
echo "=== real execution ==="
"$PY/python" examples/demo.py
echo "=== gauntlet: all layers green ==="
