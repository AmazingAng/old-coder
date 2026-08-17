#!/bin/sh
# Stable entry point for evidence.md; the Python implementation avoids shell
# pipelines that can hide an intermediate read failure.
set -eu
script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
exec python3 "$script_dir/source_state.py"
