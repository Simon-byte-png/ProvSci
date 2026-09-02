#!/usr/bin/env sh
set -eu

ROOT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$ROOT_DIR"

RUN_DIR=${1:-work/demo-run}
PYTHONPATH=src python3 -m provsci.cli run \
  --input examples/documents/generic_results_demo.json \
  --output "$RUN_DIR"

printf '\nArtifacts written to %s\n' "$RUN_DIR"
