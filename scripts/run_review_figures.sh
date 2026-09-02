#!/usr/bin/env sh
set -eu

ROOT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$ROOT_DIR"

RUN_DIR=${1:-work/review-figures}
PYTHONPATH=src python3 scripts/build_review_figures.py \
  --input examples/review/literature_matrix.json \
  --output "$RUN_DIR"

printf '\nReview matrix and figures written to %s\n' "$RUN_DIR"
