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
        predicted_rows_by_doc: dict[str, list[dict[str, Any]]] = {}
        for row in rows:
            predicted_by_doc.setdefault(row["source"]["doc_id"], set()).add(_claim_signature(row))
            predicted_rows_by_doc.setdefault(row["source"]["doc_id"], []).append(row)
        per_document = []
        for entry, (path, metadata) in zip(entries, manifest_entries):
            document = load_document(path, metadata)
            expected = entry.get("expected", {})
            expected_claims = {_expected_signature(claim) for claim in entry.get("expected_claims", [])}
            predicted = predicted_by_doc.get(document.doc_id, set())
            matched = expected_claims & predicted
            condition_claims = [claim for claim in entry.get("expected_claims", []) if "condition" in claim]
            condition_matches = 0
            predicted_rows = predicted_rows_by_doc.get(document.doc_id, [])
            for claim in condition_claims:
                signature = _expected_signature(claim)
                candidates = [row for row in predicted_rows if _claim_signature(row) == signature]
                if any(_condition_matches(row, claim.get("condition")) for row in candidates):
                    condition_matches += 1
            table_value_claims = [
                claim for claim in entry.get("expected_claims", [])
                if claim.get("kind") == "table" and "value" in claim
            ]
            table_value_matches = sum(
                any(_table_value_matches(row, claim) for row in predicted_rows)
                for claim in table_value_claims
            )
            expected_locators = {
                _expected_locator_signature(claim)
                for claim in entry.get("expected_claims", [])
            }
            predicted_locators = [
                _sample_locator_signature(row)
                for row in predicted_rows
                if _sample_locator_signature(row) is not None
            ]
            locator_matches = sum(locator in expected_locators for locator in predicted_locators)
            expected_locator_matches = sum(
                locator in set(predicted_locators) for locator in expected_locators
            )
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
                "condition_match_rate": _optional_value_rate(condition_matches, len(condition_claims)),
                "condition_claims": len(condition_claims),
                "table_value_match_rate": _optional_value_rate(table_value_matches, len(table_value_claims)),
                "table_value_claims": len(table_value_claims),
                "evidence_locator_precision": _rate(locator_matches, len(predicted_locators)),
                "evidence_locator_recall": _rate(expected_locator_matches, len(expected_locators)),
                "expected_evidence_locators": len(expected_locators),
                "predicted_evidence_locators": len(predicted_locators),
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
            "condition_match_rate": _aggregate_optional_rate(per_document, "condition_match_rate", "condition_claims"),
            "table_value_match_rate": _aggregate_optional_rate(per_document, "table_value_match_rate", "table_value_claims"),
            "evidence_locator_precision": _rate(
                sum(item["evidence_locator_precision"] * item["predicted_evidence_locators"] for item in per_document),
                sum(item["predicted_evidence_locators"] for item in per_document),
            ),
            "evidence_locator_recall": _rate(
                sum(item["evidence_locator_recall"] * item["expected_evidence_locators"] for item in per_document),
                sum(item["expected_evidence_locators"] for item in per_document),
            ),
            "runtime_seconds": summary.get("runtime_seconds", 0.0),
            "candidate_rate_per_second": summary.get("candidate_rate_per_second", 0.0),
            "estimated_cost_usd": summary.get("estimated_cost_usd", 0.0),
            "cost_basis": summary.get("cost_basis", "unknown"),
            "no_duplicate_sample_ids": not summary["duplicate_sample_ids"],
            "duplicate_groups": summary.get("duplicate_groups", 0),
            "duplicate_claims": summary.get("duplicate_claims", 0),
            "conflict_groups": summary.get("conflict_groups", 0),
            "conflict_claims": summary.get("conflict_claims", 0),
            "failure_modes": summary.get("failure_modes", {}),
            "documents": per_document,
        }
        strategy_results[strategy] = result

    full = strategy_results.get("full", {})
    focused = strategy_results.get("result_focused", {})
    table_only = strategy_results.get("table_only", {})
    result = {
        "manifest": str(manifest_file),
        "document_count": len(entries),
        "comparison_protocol": {
            "reference_strategy": "result_focused",
            "rule_baselines": ["table_only", "full"],
            "model_calls": False,
            "cost_basis": "deterministic_local_no_model_calls",
        },
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


def _sample_locator_signature(sample: dict[str, Any]) -> tuple[str, ...] | None:
    evidence = sample.get("evidence", [{}])
    if not evidence:
        return None
    item = evidence[0] or {}
    modality = str(item.get("modality", ""))
    locator = item.get("locator", {}) or {}
    if modality == "table":
        return (
            "table",
            str(locator.get("table_id", "")),
            str(locator.get("row", "")),
            str(locator.get("col", "")),
        )
    if modality in {"text", "supplement", "figure"}:
        key = {
            "text": "paragraph_id",
            "supplement": "supplement_id",
            "figure": "figure_id",
        }[modality]
        return (modality, str(locator.get(key, "")))
    return (modality,)


def _expected_locator_signature(claim: dict[str, Any]) -> tuple[str, ...]:
    kind = str(claim.get("kind", ""))
    if kind == "table":
        return (
            "table",
            str(claim.get("table_id", "")),
            str(claim.get("row", "")),
            str(claim.get("col", "")),
        )
    if kind == "relation" or kind == "text_number":
        return ("text", str(claim.get("paragraph_id", "")))
    return (kind,)


def _table_value_matches(sample: dict[str, Any], claim: dict[str, Any]) -> bool:
    """Check a table claim's value/unit/metric/entity when annotated.

    Older manifests intentionally contain locator-only table claims; this
    stricter check activates only when a claim supplies ``value``.  Numeric
    values use a small absolute tolerance to avoid treating serialization
    differences such as ``7.60`` versus ``7.6`` as errors.
    """
    evidence = sample.get("evidence", [{}])
    if not evidence or (evidence[0] or {}).get("modality") != "table":
        return False
    locator = (evidence[0] or {}).get("locator", {}) or {}
    for key in ("table_id", "row", "col"):
        if str(locator.get(key, "")) != str(claim.get(key, "")):
            return False
    answer = (sample.get("task", {}) or {}).get("answer", {}) or {}
    expected_value = claim.get("value")
    actual_value = answer.get("value")
    try:
        if abs(float(actual_value) - float(expected_value)) > max(1e-9, abs(float(expected_value)) * 1e-6):
            return False
    except (TypeError, ValueError):
        if str(actual_value).strip().casefold() != str(expected_value).strip().casefold():
            return False
    for key in ("unit", "metric", "entity"):
        if key in claim and str(answer.get(key, "")).strip().casefold() != str(claim[key]).strip().casefold():
            return False
    if "uncertainty" in claim:
        try:
            if abs(float(answer.get("uncertainty")) - float(claim["uncertainty"])) > 1e-6:
                return False
        except (TypeError, ValueError):
            return False
    return True


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


def _condition_matches(sample: dict[str, Any], expected: Any) -> bool:
    """Compare an annotated condition with a predicted ResultCard condition."""
    card_condition = (sample.get("result_card", {}) or {}).get("condition", {}) or {}
    actual_text = " ".join(str(card_condition.get("text", "")).split()).casefold()
    if isinstance(expected, dict):
        expected_text = " ".join(str(expected.get("text", "")).split()).casefold()
        expected_status = str(expected.get("status", "")).casefold()
        if expected_status and str(card_condition.get("status", "")).casefold() != expected_status:
            return False
    else:
        expected_text = " ".join(str(expected).split()).casefold()
    return actual_text == expected_text


def _optional_rate(rows: list[dict[str, Any]], key: str) -> float | None:
    values = [row[key] for row in rows if row[key] is not None]
    return _rate(sum(values), len(values)) if values else None


def _optional_value_rate(numerator: int, denominator: int) -> float | None:
    return _rate(numerator, denominator) if denominator else None


def _aggregate_optional_rate(rows: list[dict[str, Any]], rate_key: str, count_key: str) -> float | None:
    eligible = [row for row in rows if row.get(rate_key) is not None and row.get(count_key, 0)]
    denominator = sum(int(row.get(count_key, 0)) for row in eligible)
    numerator = sum(float(row[rate_key]) * int(row.get(count_key, 0)) for row in eligible)
    return round(numerator / denominator, 4) if denominator else None


def _rate(numerator: int, denominator: int) -> float:
    return round(numerator / denominator, 4) if denominator else 0.0
