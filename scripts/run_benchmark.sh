#!/usr/bin/env sh
set -eu

ROOT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$ROOT_DIR"

RUN_DIR=${1:-work/benchmark}
MANIFEST=${2:-examples/benchmark/p0-gold-manifest.json}
PYTHONPATH=src python3 -m provsci.cli evaluate \
  --manifest "$MANIFEST" \
  --output "$RUN_DIR"

printf '\nBenchmark artifacts written to %s\n' "$RUN_DIR"
