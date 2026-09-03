#!/usr/bin/env sh
set -eu

ROOT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
HOST=${1:-127.0.0.1}
PORT=${2:-4173}

if ! command -v python3 >/dev/null 2>&1; then
  printf '%s\n' '未找到 Python 3.9+，请先安装 Python。' >&2
  exit 1
fi

cd "$ROOT_DIR"
PYTHONPATH="$ROOT_DIR/src${PYTHONPATH:+:$PYTHONPATH}" \
  exec python3 scripts/run_product_app.py "$HOST" "$PORT"
