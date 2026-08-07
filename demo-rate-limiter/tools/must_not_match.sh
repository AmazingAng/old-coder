# Must-find-nothing grep, fail closed: grep rc 1 (no matches) is the only
# pass; grep rc 0 = forbidden pattern present (we return 1), grep rc >= 2 =
# the check itself broke (we return 2, so the self-test can tell the two
# failure modes apart). Any nonzero return fails the gauntlet under set -e.
# Sourced by tools/gauntlet.sh; exercised by tools/test_gauntlet_checks.sh.
must_not_match() {
  pattern=$1; shift
  if grep -rniE "$pattern" "$@"; then
    echo "FAIL: forbidden pattern present: $pattern"; return 1
  elif [ $? -ne 1 ]; then
    echo "FAIL: scan itself broke (fail closed): $pattern"; return 2
  fi
}
