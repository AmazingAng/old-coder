# Must-find-nothing grep, fail closed: rc 1 (no matches) is the only pass;
# rc 0 = forbidden pattern present, rc >= 2 = the check itself broke.
# Sourced by tools/gauntlet.sh; exercised by tools/test_gauntlet_checks.sh.
must_not_match() {
  pattern=$1; shift
  if grep -rniE "$pattern" "$@"; then
    echo "FAIL: forbidden pattern present: $pattern"; return 1
  elif [ $? -ne 1 ]; then
    echo "FAIL: scan itself broke (fail closed): $pattern"; return 1
  fi
}
