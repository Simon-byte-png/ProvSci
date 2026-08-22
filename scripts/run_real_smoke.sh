#!/usr/bin/env sh
set -eu

ROOT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$ROOT_DIR"

RUN_DIR=${1:-work/real-smoke}
PYTHONPATH=src python3 -m provsci.cli batch \
  --manifest examples/benchmark/real-smoke-manifest.json \
  --output "$RUN_DIR" \
  --strategy result_focused

printf '\nReal-paper smoke artifacts written to %s\n' "$RUN_DIR"
