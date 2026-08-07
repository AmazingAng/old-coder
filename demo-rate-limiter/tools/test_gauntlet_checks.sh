#!/bin/sh
# Regression check for the fail-closed must-not scan.
#
# It sources the real helper rather than copying it: a copy would keep passing
# after must_not_match itself regressed, which is the exact failure mode this
# check exists to prevent.
cd "$(dirname "$0")/.."
. tools/must_not_match.sh

failures=0

expect() {
  want=$1; got=$2; what=$3
  if [ "$got" -eq "$want" ]; then
    echo "  ok: $what (rc=$got)"
  else
    echo "  NOT OK: $what (want rc $want, got rc $got)"
    failures=$((failures + 1))
  fi
}

work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT INT TERM
mkdir "$work/tree"
printf 'nothing to see here\n' > "$work/tree/clean.txt"

# 1. Forbidden pattern present -> must fail.
printf 'FORBIDDEN marker\n' > "$work/tree/dirty.txt"
must_not_match 'forbidden' "$work/tree" >/dev/null 2>&1
expect 1 $? "forbidden pattern present fails"

# 2. Nothing to find -> must pass. Guards against a check that can never pass.
rm "$work/tree/dirty.txt"
must_not_match 'forbidden' "$work/tree" >/dev/null 2>&1
expect 0 $? "clean tree passes"

# 3. The scan itself breaks -> must fail with rc 2, distinct from the
#    pattern-present rc 1, so a regression that mixes up the two failure
#    branches cannot pass. This is the fail-open guard: grep exits >= 2 here,
#    which must never be read as "no matches". A nonexistent path is used
#    rather than an unreadable (chmod 000) file: root can still read a
#    chmod-000 file, so that variant would need a skip branch to stay
#    portable, and a silent skip is the thing this check exists to prevent.
must_not_match 'forbidden' "$work/tree/no-such-path" >/dev/null 2>&1
expect 2 $? "broken scan fails closed"

if [ "$failures" -ne 0 ]; then
  echo "FAIL: $failures fail-closed expectation(s) violated"
  exit 1
fi
echo "checker self-test clean"
