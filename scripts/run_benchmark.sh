#!/usr/bin/env sh
set -eu

ROOT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$ROOT_DIR"

RUN_DIR=${1:-work/benchmark}
PYTHONPATH=src python3 -m provsci.cli evaluate \
  --manifest examples/benchmark/manifest.json \
  --output "$RUN_DIR"

printf '\nBenchmark artifacts written to %s\n' "$RUN_DIR"
