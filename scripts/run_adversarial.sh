#!/usr/bin/env sh
set -eu

ROOT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$ROOT_DIR"

RUN_ROOT=${1:-work/adversarial-evaluation}
MANIFEST=${2:-examples/benchmark/p0-gold-manifest.json}
mkdir -p "$RUN_ROOT"

PYTHONPATH=src python3 -m provsci.cli adversarial \
  --manifest "$MANIFEST" \
  --output "$RUN_ROOT" \
  --strategy result_focused

printf '\nAdversarial evaluation artifacts written to %s\n' "$RUN_ROOT"
