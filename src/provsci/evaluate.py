"""Small reproducible benchmark runner for the deterministic baseline."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .adapters import load_document
from .batch import read_manifest_entries, run_batch


def evaluate_manifest(
    manifest_path: str | Path,
    output_dir: str | Path,
    strategies: tuple[str, ...] = ("table_only", "full", "result_focused"),
) -> dict[str, Any]:
    manifest_file = Path(manifest_path)
    raw = json.loads(manifest_file.read_text(encoding="utf-8"))
    entries = raw.get("documents", [])
    manifest_entries = read_manifest_entries(manifest_file)
    paths = [path for path, _ in manifest_entries]
    output = Path(output_dir)
    strategy_results: dict[str, Any] = {}
    for strategy in strategies:
        strategy_output = output / strategy
        summary = run_batch(manifest_entries, strategy_output, strategy=strategy)
        observed = {item["doc_id"]: item for item in summary["documents"]}
        rows = _read_jsonl(strategy_output / "all.jsonl")
        predicted_by_doc: dict[str, set[tuple[str, ...]]] = {}
        for row in rows:
            predicted_by_doc.setdefault(row["source"]["doc_id"], set()).add(_claim_signature(row))
        per_document = []
        for entry, (path, metadata) in zip(entries, manifest_entries):
            document = load_document(path, metadata)
            expected = entry.get("expected", {})
            expected_claims = {_expected_signature(claim) for claim in entry.get("expected_claims", [])}
            predicted = predicted_by_doc.get(document.doc_id, set())
            matched = expected_claims & predicted
            actual = observed.get(document.doc_id, {})
            per_document.append({
                "doc_id": document.doc_id,
                "expected": expected,
                "actual": actual,
                "expected_claims": len(expected_claims),
                "matched_claims": len(matched),
                "predicted_claims": len(predicted),
                "claim_recall": _rate(len(matched), len(expected_claims)),
                "claim_precision": _rate(len(matched), len(predicted)),
                "candidate_count_match": actual.get("candidates") == expected.get("candidates") if "candidates" in expected else None,
                "gold_count_match": actual.get("gold") == expected.get("gold") if "gold" in expected else None,
                "silver_count_match": actual.get("silver") == expected.get("silver") if "silver" in expected else None,
            })
        count = len(per_document)
        result = {
            "strategy": strategy,
            "manifest": str(manifest_file),
            "document_count": count,
            "candidate_count_accuracy": _optional_rate(per_document, "candidate_count_match"),
            "gold_count_accuracy": _optional_rate(per_document, "gold_count_match"),
            "silver_count_accuracy": _optional_rate(per_document, "silver_count_match"),
            "claim_recall": _rate(sum(item["matched_claims"] for item in per_document), sum(item["expected_claims"] for item in per_document)),
            "claim_precision": _rate(sum(item["matched_claims"] for item in per_document), sum(item["predicted_claims"] for item in per_document)),
            "path_reproducibility": summary["path_reproducibility"],
            "evidence_coverage": summary["evidence_coverage"],
            "license_coverage": summary["license_coverage"],
            "no_duplicate_sample_ids": not summary["duplicate_sample_ids"],
            "documents": per_document,
        }
        strategy_results[strategy] = result

    full = strategy_results.get("full", {})
    focused = strategy_results.get("result_focused", {})
    table_only = strategy_results.get("table_only", {})
    result = {
        "manifest": str(manifest_file),
        "document_count": len(entries),
        "strategies": strategy_results,
        "improvement_full_minus_table_only": {
            "claim_recall": round(full.get("claim_recall", 0.0) - table_only.get("claim_recall", 0.0), 4),
            "claim_precision": round(full.get("claim_precision", 0.0) - table_only.get("claim_precision", 0.0), 4),
            "gold_count_accuracy": round(full.get("gold_count_accuracy", 0.0) - table_only.get("gold_count_accuracy", 0.0), 4),
        },
        "improvement_result_focused_minus_table_only": {
            "claim_recall": round(focused.get("claim_recall", 0.0) - table_only.get("claim_recall", 0.0), 4),
            "claim_precision": round(focused.get("claim_precision", 0.0) - table_only.get("claim_precision", 0.0), 4),
            "gold_count_accuracy": round(focused.get("gold_count_accuracy", 0.0) - table_only.get("gold_count_accuracy", 0.0), 4),
        },
    }
    (output / "evaluation.json").write_text(json.dumps(result, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    return result


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _claim_signature(sample: dict[str, Any]) -> tuple[str, ...]:
    task_type = str(sample.get("task", {}).get("type", ""))
    evidence = sample.get("evidence", [{}])[0]
    modality = str(evidence.get("modality", ""))
    locator = evidence.get("locator", {})
    if modality == "table":
        return ("table", task_type, str(locator.get("table_id", "")), str(locator.get("row", "")), str(locator.get("col", "")))
    if task_type == "relation":
        answer = sample.get("task", {}).get("answer", {})
        return (
            "relation",
            str(locator.get("paragraph_id", "")),
            str(answer.get("value", "")).casefold(),
            str(answer.get("subject", "")).casefold(),
            str(answer.get("object", "")).casefold(),
        )
    answer = sample.get("task", {}).get("answer", {})
    return (
        "text_number",
        str(locator.get("paragraph_id", "")),
        str(answer.get("value", "")),
        str(answer.get("unit", "")),
        str(answer.get("metric", "")).casefold(),
        str(answer.get("entity", "")).casefold(),
    )


def _expected_signature(claim: dict[str, Any]) -> tuple[str, ...]:
    kind = str(claim.get("kind", ""))
    if kind == "table":
        return ("table", str(claim.get("task_type", "numeric_qa")), str(claim["table_id"]), str(claim["row"]), str(claim["col"]))
    if kind == "relation":
        return (
            "relation",
            str(claim["paragraph_id"]),
            str(claim["value"]).casefold(),
            str(claim["subject"]).casefold(),
            str(claim["object"]).casefold(),
        )
    if kind == "text_number":
        return (
            "text_number",
            str(claim["paragraph_id"]),
            str(claim["value"]),
            str(claim["unit"]),
            str(claim["metric"]).casefold(),
            str(claim["entity"]).casefold(),
        )
    raise ValueError(f"unknown expected claim kind: {kind}")


def _optional_rate(rows: list[dict[str, Any]], key: str) -> float | None:
    values = [row[key] for row in rows if row[key] is not None]
    return _rate(sum(values), len(values)) if values else None


def _rate(numerator: int, denominator: int) -> float:
    return round(numerator / denominator, 4) if denominator else 0.0
