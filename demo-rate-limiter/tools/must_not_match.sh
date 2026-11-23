# Must-find-nothing grep, fail closed: grep rc 1 (no matches) is the only
# pass; grep rc 0 = forbidden pattern present (we return 1), grep rc >= 2 =
# the check itself broke (we return 2, so the self-test can tell the two
# failure modes apart). Any nonzero return fails the gauntlet under set -e.
# Only file:line is printed, never the matching text: when the pattern is a
# credential scan, echoing the line copies a leaked credential into CI logs.
# Sourced by tools/gauntlet.sh; exercised by tools/test_gauntlet_checks.sh.
must_not_match() {
  pattern=$1; shift
  # -H: with a single file argument grep omits the name, and cut would then
  # print the start of the matching line instead of file:line.
  _mnm_hits=$(grep -rniHE "$pattern" "$@")
  _mnm_rc=$?
  if [ "$_mnm_rc" -eq 0 ]; then
    printf '%s\n' "$_mnm_hits" | cut -d: -f1,2
    echo "FAIL: forbidden pattern present: $pattern"; return 1
  elif [ "$_mnm_rc" -ne 1 ]; then
    echo "FAIL: scan itself broke (fail closed): $pattern"; return 2
  fi
}
