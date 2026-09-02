"""Diagnostic module-ablation reports for the fixed ProvSci benchmark."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

from .batch import read_manifest_entries, run_batch
from .evaluate import _claim_signature, _expected_signature, _rate
from .verifier import is_known_license


# ``quality.needs_human_review`` is deliberately broad in the runtime
# pipeline: verifier failures and unknown licences also enter the review queue.
# For an ablation, those concerns must remain attributable to their own gate.
_NON_QUALITY_FAILURES = {
    "license_unknown",
    "missing_evidence",
    "evidence_mismatch",
    "evidence_not_found",
    "unsupported_evidence_modality",
    "missing_acquisition_path",
    "path_execution_error",
    "answer_mismatch",
    "human_accept_unverified",
}


def evaluate_module_ablation(
    manifest_path: str | Path,
    output_dir: str | Path,
    strategy: str = "result_focused",
) -> dict[str, Any]:
    """Measure which quality gates change the retained fixed-set results.

    This is an offline diagnostic, not a production mode.  Every variant
    mines the same documents once and only changes the final inclusion rule:

    ``all_gates`` requires every gate; each ``without_*`` variant removes one
    gate while retaining the others.  Evidence and acquisition-path presence
    are reported as separate gates because they are independently auditable,
    even though the verifier also checks them before a sample can pass.
    These variants must never be used to write a production Gold dataset.
    """
    manifest = Path(manifest_path)
    raw = json.loads(manifest.read_text(encoding="utf-8"))
    entries = raw.get("documents", [])
    manifest_entries = read_manifest_entries(manifest)
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    run_output = output / "run"
    summary = run_batch(manifest_entries, run_output, strategy=strategy)
    rows = _read_jsonl(run_output / "all.jsonl")
    expected_by_doc: dict[str, set[tuple[str, ...]]] = {}
    for entry, (path, metadata) in zip(entries, manifest_entries):
        # The manifest entry is authoritative for the expected claims; the
        # path/metadata pair is consumed by run_batch above.
        expected_by_doc[str(_doc_id_for_entry(rows, entry, metadata, path))] = {
            _expected_signature(claim) for claim in entry.get("expected_claims", [])
        }

    gate_names = ("quality", "verifier", "license", "evidence", "acquisition_path")
    gate_rejection_counts = {
        name: sum(not _gate_states(row)[name] for row in rows)
        for name in gate_names
    }
    required_gates = {
        "all_gates": gate_names,
        "without_quality_gate": tuple(name for name in gate_names if name != "quality"),
        "without_verifier": tuple(name for name in gate_names if name != "verifier"),
        "without_license_gate": tuple(name for name in gate_names if name != "license"),
        "without_evidence_path_gate": tuple(
            name for name in gate_names if name not in {"evidence", "acquisition_path"}
        ),
    }
    variants: dict[str, Callable[[dict[str, Any]], bool]] = {
        name: _require_gates(gates) for name, gates in required_gates.items()
    }
    reports = {name: _variant_report(rows, expected_by_doc, predicate) for name, predicate in variants.items()}
    result = {
        "manifest": str(manifest),
        "strategy": strategy,
        "document_count": summary.get("document_count", len(manifest_entries)),
        "candidate_count": len(rows),
        "production_baseline": "all_gates",
        "diagnostic_warning": "without_* variants are not safe for production Gold export",
        "gate_names": list(gate_names),
        "gate_rejection_counts": gate_rejection_counts,
        "variants": reports,
        "gate_deltas": {
            name: {
                "gold_like_delta_vs_all_gates": report["gold_like_count"] - reports["all_gates"]["gold_like_count"],
                "claim_precision_delta_vs_all_gates": round(report["claim_precision"] - reports["all_gates"]["claim_precision"], 4),
            }
            for name, report in reports.items()
            if name != "all_gates"
        },
    }
    (output / "ablation.json").write_text(json.dumps(result, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    return result


def _gate_states(sample: dict[str, Any]) -> dict[str, bool]:
    """Return independent gate states for one candidate.

    The states intentionally describe the observable contract rather than
    trying to infer the verifier's internal failure precedence.  This makes
    the ablation report useful for diagnosing overlapping failure modes.
    """
    quality = sample.get("quality", {}) or {}
    verification = sample.get("verification", {}) or {}
    source = sample.get("source", {}) or {}
    failure_mode = str(quality.get("failure_mode") or "")
    quality_ok = (
        failure_mode in _NON_QUALITY_FAILURES
        or (
            not bool(quality.get("needs_human_review", False))
            and quality.get("review_disposition") != "rejected"
        )
    )
    if quality.get("review_disposition") == "rejected" or failure_mode == "human_rejected":
        quality_ok = False
    return {
        "quality": quality_ok,
        "verifier": verification.get("status") == "pass",
        "license": is_known_license(source.get("license")),
        "evidence": bool(sample.get("evidence")),
        "acquisition_path": bool(sample.get("acquisition_path")),
    }


def _require_gates(gates: tuple[str, ...]) -> Callable[[dict[str, Any]], bool]:
    """Build a predicate requiring exactly the requested gate subset."""
    return lambda sample: all(_gate_states(sample).get(name, False) for name in gates)


def _variant_report(
    rows: list[dict[str, Any]],
    expected_by_doc: dict[str, set[tuple[str, ...]]],
    include: Callable[[dict[str, Any]], bool],
) -> dict[str, Any]:
    selected = [row for row in rows if include(row)]
    predicted_by_doc: dict[str, set[tuple[str, ...]]] = {}
    for row in selected:
        predicted_by_doc.setdefault(row.get("source", {}).get("doc_id", ""), set()).add(_claim_signature(row))
    doc_ids = set(expected_by_doc) | set(predicted_by_doc)
    expected_count = sum(len(expected_by_doc.get(doc_id, set())) for doc_id in doc_ids)
    predicted_count = sum(len(predicted_by_doc.get(doc_id, set())) for doc_id in doc_ids)
    matched_count = sum(
        len(expected_by_doc.get(doc_id, set()) & predicted_by_doc.get(doc_id, set()))
        for doc_id in doc_ids
    )
    unmatched_count = sum(
        len(predicted_by_doc.get(doc_id, set()) - expected_by_doc.get(doc_id, set()))
        for doc_id in doc_ids
    )
    return {
        "selected_count": len(selected),
        "gold_like_count": len(selected),
        "gold_yield": _rate(len(selected), len(rows)),
        "claim_recall": _rate(matched_count, expected_count),
        "claim_precision": _rate(matched_count, predicted_count),
        "unmatched_candidate_rate": _rate(unmatched_count, predicted_count),
        "evidence_coverage": _rate(sum(bool(row.get("evidence")) for row in selected), len(selected)),
        "license_coverage": _rate(sum(is_known_license(row.get("source", {}).get("license")) for row in selected), len(selected)),
        "path_reproducibility": _rate(sum(row.get("verification", {}).get("status") == "pass" for row in selected), len(selected)),
    }


def _doc_id_for_entry(
    rows: list[dict[str, Any]], entry: dict[str, Any], metadata: dict[str, Any], path: Path,
) -> str:
    if metadata.get("doc_id"):
        return str(metadata["doc_id"])
    for row in rows:
        if row.get("source", {}).get("local_path") == str(path):
            return str(row.get("source", {}).get("doc_id", ""))
    # Every current manifest has either metadata.doc_id or at least one row;
    # this fallback keeps empty-candidate documents represented in the report.
    return str(entry.get("doc_id", path.stem))


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
