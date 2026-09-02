#!/usr/bin/env sh
set -eu

ROOT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$ROOT_DIR"

RUN_ROOT=${1:-work/p0-final}
mkdir -p "$RUN_ROOT"

sh scripts/run_demo.sh "$RUN_ROOT/demo"
sh scripts/run_benchmark.sh "$RUN_ROOT/benchmark" examples/benchmark/p0-gold-manifest.json
sh scripts/run_real_smoke.sh "$RUN_ROOT/real-smoke"

printf '\nP0 reproducibility artifacts written to %s\n' "$RUN_ROOT"
