#!/bin/sh
# Negative controls for the gauntlet's layer-completion contract.
cd "$(dirname "$0")/.."

failures=0

expect_rc() {
  want=$1; got=$2; what=$3
  if [ "$got" -eq "$want" ]; then
    echo "  ok: $what (rc=$got)"
  else
    echo "  NOT OK: $what (want rc $want, got rc $got)"
    failures=$((failures + 1))
  fi
}

expect_contains() {
  output=$1; needle=$2; what=$3
  case "$output" in
    *"$needle"*) echo "  ok: $what" ;;
    *)
      echo "  NOT OK: $what (missing: $needle)"
      failures=$((failures + 1))
      ;;
  esac
}

expect_absent() {
  output=$1; needle=$2; what=$3
  case "$output" in
    *"$needle"*)
      echo "  NOT OK: $what (unexpected: $needle)"
      failures=$((failures + 1))
      ;;
    *) echo "  ok: $what" ;;
  esac
}

# 1. Omitting an expected layer must make the final audit fail and name it.
output=$({
  . tools/gauntlet_layers.sh
  for layer in $GAUNTLET_EXPECTED_LAYERS; do
    [ "$layer" = mutation ] || run_layer "$layer" true
  done
  finish_gauntlet
} 2>&1)
rc=$?
expect_rc 1 "$rc" "omitted layer fails the final audit"
expect_contains "$output" "missing layer 'mutation'" "omitted layer is named"
expect_absent "$output" "all layers green" "omitted layer cannot report green"

# 2. A broken command must preserve its status, name its layer and stop before
#    later work. This specifically guards against relying on set -e through an
#    AND-list or another conditional context.
output=$(sh -c '
  set -e
  . tools/gauntlet_layers.sh
  run_layer mutation sh -c "exit 7"
  echo LATER-LAYER-RAN
' 2>&1)
rc=$?
expect_rc 7 "$rc" "failed command status is preserved"
expect_contains "$output" "layer 'mutation' failed (rc=7)" "failed layer is named"
expect_absent "$output" "LATER-LAYER-RAN" "failed command stops later work"
expect_absent "$output" "all layers green" "failed command cannot report green"

# 3. A typo in a layer name must not create a new, unrequired layer.
output=$(sh -c '
  . tools/gauntlet_layers.sh
  run_layer mutatoin true
' 2>&1)
rc=$?
expect_rc 2 "$rc" "unknown layer fails"
expect_contains "$output" "unknown layer 'mutatoin'" "unknown layer is named"

# 4. Re-running one cheap layer must not stand in for a missing layer.
output=$(sh -c '
  . tools/gauntlet_layers.sh
  run_layer mutation true
  run_layer mutation true
' 2>&1)
rc=$?
expect_rc 2 "$rc" "duplicate layer fails"
expect_contains "$output" "duplicate layer 'mutation'" "duplicate layer is named"

# 5. The controls are not a script that can only fail: one successful command
#    for every expected layer reaches the one legitimate all-green message.
output=$(
  . tools/gauntlet_layers.sh
  for layer in $GAUNTLET_EXPECTED_LAYERS; do
    run_layer "$layer" true
  done
  finish_gauntlet
) 2>&1
rc=$?
expect_rc 0 "$rc" "complete manifest passes"
expect_contains "$output" "=== gauntlet: all layers green ===" "complete manifest reports green"

if [ "$failures" -ne 0 ]; then
  echo "FAIL: $failures orchestration expectation(s) violated"
  exit 1
fi
echo "orchestration self-test clean"
