#!/usr/bin/env sh
set -eu

ROOT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$ROOT_DIR"

RUN_ROOT=${1:-work/p2-evaluation}
MANIFEST=${2:-examples/benchmark/p0-gold-manifest.json}
mkdir -p "$RUN_ROOT"

sh scripts/run_benchmark.sh "$RUN_ROOT/benchmark" "$MANIFEST"
PYTHONPATH=src python3 -m provsci.cli ablate \
  --manifest "$MANIFEST" \
  --output "$RUN_ROOT/ablation" \
  --strategy result_focused

PYTHONPATH=src python3 -m provsci.cli adversarial \
  --manifest "$MANIFEST" \
  --output "$RUN_ROOT/adversarial" \
  --strategy result_focused

printf '\nP2 evaluation artifacts written to %s\n' "$RUN_ROOT"
