#!/bin/sh
# Fail-closed execution and completion accounting for the gauntlet entry point.
GAUNTLET_EXPECTED_LAYERS="orchestration-self-test checker-self-test source-state-self-test tests-coverage types lint-format supply-chain must-not-scans mutation-control mutation real-execution source-state"
GAUNTLET_COMPLETED_LAYERS=""

run_layer() {
  if [ "$#" -lt 2 ]; then
    echo "FAIL: run_layer requires a layer name and command" >&2
    return 2
  fi

  layer=$1
  shift

  case " $GAUNTLET_EXPECTED_LAYERS " in
    *" $layer "*) ;;
    *)
      echo "FAIL: unknown layer '$layer'" >&2
      return 2
      ;;
  esac

  case " $GAUNTLET_COMPLETED_LAYERS " in
    *" $layer "*)
      echo "FAIL: duplicate layer '$layer'" >&2
      return 2
      ;;
  esac

  printf '=== %s ===\n' "$layer"
  if "$@"; then
    GAUNTLET_COMPLETED_LAYERS="$GAUNTLET_COMPLETED_LAYERS $layer"
    return 0
  else
    rc=$?
    printf "FAIL: layer '%s' failed (rc=%s)\n" "$layer" "$rc" >&2
    return "$rc"
  fi
}

finish_gauntlet() {
  missing=0
  for layer in $GAUNTLET_EXPECTED_LAYERS; do
    case " $GAUNTLET_COMPLETED_LAYERS " in
      *" $layer "*) ;;
      *)
        echo "FAIL: missing layer '$layer'" >&2
        missing=1
        ;;
    esac
  done

  if [ "$missing" -ne 0 ]; then
    return 1
  fi
  echo "=== gauntlet: all layers green ==="
}
