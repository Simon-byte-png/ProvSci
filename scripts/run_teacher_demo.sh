#!/usr/bin/env sh
set -eu

ROOT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$ROOT_DIR"

RUN_ROOT=${1:-work/teacher-demo-v2}
P0_ROOT="$RUN_ROOT/p0"
REAL_ROOT="$P0_ROOT/real-smoke"
QUERY_JSON="$REAL_ROOT/query_sw480_ic50.json"
QUERY_PREVIEW="$REAL_ROOT/query_sw480_ic50_preview.json"
BENCH_JSON="$P0_ROOT/benchmark/evaluation.json"

mkdir -p "$RUN_ROOT"

printf '%s\n' "[1/5] Running the reproducible P0 loop..."
sh scripts/run_p0.sh "$P0_ROOT"

printf '%s\n' "[2/5] Running the teacher-demo natural-language query..."
PYTHONPATH=src python3 -m provsci.cli ask \
  --results "$REAL_ROOT" \
  --question "What IC50 was reported for SW480 under 24 h?" \
  --limit 3 > "$QUERY_JSON"

printf '%s\n' "[3/5] Building a compact query preview and review queue snapshot..."
PYTHONPATH=src python3 - "$QUERY_JSON" "$QUERY_PREVIEW" <<'PY'
import json
import sys

query_path, preview_path = sys.argv[1:]
items = json.load(open(query_path, encoding="utf-8"))
if items:
    item = items[0]
    preview = {
        "question": item.get("task", {}).get("question"),
        "answer": item.get("task", {}).get("answer"),
        "result_card": item.get("result_card"),
        "evidence": item.get("evidence"),
        "path": item.get("acquisition_path"),
        "verification": item.get("verification"),
    }
else:
    preview = {
        "question": "What IC50 was reported for SW480 under 24 h?",
        "results": [],
    }
with open(preview_path, "w", encoding="utf-8") as handle:
    json.dump(preview, handle, indent=2, ensure_ascii=False)
    handle.write("\n")
PY
PYTHONPATH=src python3 -m provsci.cli review-queue \
  --run "$REAL_ROOT" \
  > "$RUN_ROOT/review_queue_summary.json"

printf '%s\n' "[4/5] Rendering the local review workbench..."
PYTHONPATH=src python3 -m provsci.cli review-ui \
  --run "$REAL_ROOT" \
  --output "$REAL_ROOT/review_workbench.html" \
  > "$RUN_ROOT/review_ui_summary.json"

printf '%s\n' "[5/5] Building the visual teacher dashboard..."
PYTHONPATH=src python3 scripts/build_teacher_dashboard.py \
  "$RUN_ROOT" \
  "$RUN_ROOT/teacher_dashboard.html" \
  > "$RUN_ROOT/dashboard_path.txt"

PYTHONPATH=src python3 - "$REAL_ROOT/summary.json" "$BENCH_JSON" "$RUN_ROOT" <<'PY'
import json
import sys

real_path, benchmark_path, run_root = sys.argv[1:]
real = json.load(open(real_path, encoding="utf-8"))
benchmark = json.load(open(benchmark_path, encoding="utf-8"))
focused = benchmark["strategies"]["result_focused"]
print()
print("Teacher demo artifacts written to %s" % run_root)
print(
    "Real-paper smoke: %d docs, %d candidates, %d Gold, %d Silver/Human Review, "
    "path reproducibility %.4f, evidence coverage %.4f"
    % (
        real["document_count"],
        real["total_candidates"],
        real["gold"],
        real["human_review"],
        real["path_reproducibility"],
        real["evidence_coverage"],
    )
)
print(
    "P0 result_focused: claim recall %.4f, precision %.4f, locator P/R %.4f/%.4f "
    "on %d manually checked claims"
    % (
        focused["claim_recall"],
        focused["claim_precision"],
        focused["evidence_locator_precision"],
        focused["evidence_locator_recall"],
        52,
    )
)
print("Query: %s" % (run_root + "/p0/real-smoke/query_sw480_ic50_preview.json"))
print("Review UI: %s" % (run_root + "/p0/real-smoke/review_workbench.html"))
print("Visual dashboard: %s" % (run_root + "/teacher_dashboard.html"))
PY
