"""Deterministic contamination cases for auditing verifier behaviour.

The fixed P0 manifest is intentionally clean, so a verifier ablation on it
cannot show whether tampered answers, evidence, or paths are rejected.  This
module derives a small, reproducible diagnostic set from the same manifest.
It never mutates the source documents or the production run; each case is a
copy of a clean candidate with one controlled field change, then re-verified
against the original document.
"""

from __future__ import annotations

import copy
import json
from collections import Counter
from pathlib import Path
from typing import Any, Callable

from .adapters import load_document
from .ablation import _gate_states
from .batch import read_manifest_entries, run_batch
from .verifier import verify_sample


Mutation = Callable[[dict[str, Any]], dict[str, Any]]


def evaluate_adversarial_cases(
    manifest_path: str | Path,
    output_dir: str | Path,
    strategy: str = "result_focused",
) -> dict[str, Any]:
    """Create and verify controlled contamination cases.

    The clean candidates are mined exactly once.  One suitable candidate is
    copied for each mutation recipe, and the mutated copy is verified against
    its source document.  Missing recipes are reported rather than silently
    dropping coverage (for example, a manifest without numeric claims cannot
    provide a numeric answer-tampering case).
    """
    manifest = Path(manifest_path)
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    entries = read_manifest_entries(manifest)
    clean_output = output / "clean"
    clean_summary = run_batch(entries, clean_output, strategy=strategy)
    clean_rows = _read_jsonl(clean_output / "all.jsonl")
    documents = {
        document.doc_id: document
        for path, metadata in entries
        for document in (load_document(path, metadata),)
    }

    recipes: tuple[tuple[str, tuple[str, ...], Mutation], ...] = (
        ("tampered_answer", ("answer_mismatch",), _tamper_answer),
        ("tampered_evidence", ("evidence_mismatch",), _tamper_evidence),
        ("missing_evidence", ("missing_evidence",), _remove_evidence),
        ("missing_acquisition_path", ("missing_acquisition_path",), _remove_path),
        ("invalid_path_action", ("path_execution_error",), _tamper_path_action),
    )
    used_base_ids: set[str] = set()
    cases: list[dict[str, Any]] = []
    missing: list[str] = []
    for name, expected_modes, mutation in recipes:
        base = _select_base(clean_rows, name, used_base_ids)
        if base is None:
            missing.append(name)
            continue
        used_base_ids.add(str(base.get("id", "")))
        case = copy.deepcopy(base)
        base_id = str(base.get("id", ""))
        case["id"] = f"{base_id}__adversarial__{name}"
        case.setdefault("adversarial", {})
        case["adversarial"].update({
            "case": name,
            "base_sample_id": base_id,
            "expected_failure_modes": list(expected_modes),
        })
        mutation(case)
        document = documents.get(str(case.get("source", {}).get("doc_id", "")))
        if document is None:
            observed_mode = "source_document_not_found"
            case.setdefault("verification", {})["status"] = "fail"
            case.setdefault("quality", {})["failure_mode"] = observed_mode
        else:
            verify_sample(case, document)
            observed_mode = str(case.get("quality", {}).get("failure_mode") or "")
        states = _gate_states(case)
        case["adversarial"].update({
            "observed_failure_mode": observed_mode,
            "verifier_rejected": case.get("verification", {}).get("status") != "pass",
            "gate_states": states,
            "would_be_selected_without_verifier": all(
                states[name] for name in ("quality", "license", "evidence", "acquisition_path")
            ),
        })
        cases.append(case)

    observed_modes = Counter(
        str(case.get("adversarial", {}).get("observed_failure_mode", ""))
        for case in cases
    )
    expected_cases = len(cases)
    rejected = sum(bool(case.get("adversarial", {}).get("verifier_rejected")) for case in cases)
    bypass_selected = sum(
        bool(case.get("adversarial", {}).get("would_be_selected_without_verifier"))
        for case in cases
    )
    result = {
        "manifest": str(manifest),
        "strategy": strategy,
        "clean_summary": {
            key: clean_summary.get(key)
            for key in (
                "document_count",
                "total_candidates",
                "gold",
                "silver",
                "path_reproducibility",
            )
        },
        "case_count": expected_cases,
        "requested_case_count": len(recipes),
        "missing_cases": missing,
        "verifier_rejection_count": rejected,
        "verifier_rejection_rate": _rate(rejected, expected_cases),
        "would_be_selected_without_verifier_count": bypass_selected,
        "would_be_selected_without_verifier_rate": _rate(bypass_selected, expected_cases),
        "expected_failure_mode_counts": dict(Counter(mode for _, modes, _ in recipes for mode in modes)),
        "observed_failure_mode_counts": dict(observed_modes),
        "all_cases_rejected": expected_cases == len(recipes) and rejected == expected_cases,
        "cases": [
            {
                "case": case.get("adversarial", {}).get("case"),
                "base_sample_id": case.get("adversarial", {}).get("base_sample_id"),
                "expected_failure_modes": case.get("adversarial", {}).get("expected_failure_modes", []),
                "observed_failure_mode": case.get("adversarial", {}).get("observed_failure_mode"),
                "verification_status": case.get("verification", {}).get("status"),
                "verifier_rejected": case.get("adversarial", {}).get("verifier_rejected", False),
                "gate_states": case.get("adversarial", {}).get("gate_states", {}),
                "would_be_selected_without_verifier": case.get("adversarial", {}).get("would_be_selected_without_verifier", False),
            }
            for case in cases
        ],
    }
    _write_jsonl(output / "adversarial.jsonl", cases)
    (output / "adversarial_summary.json").write_text(
        json.dumps(result, indent=2, ensure_ascii=True) + "\n", encoding="utf-8"
    )
    return result


def _select_base(rows: list[dict[str, Any]], recipe: str, used: set[str]) -> dict[str, Any] | None:
    for row in rows:
        if str(row.get("id", "")) in used:
            continue
        answer = row.get("task", {}).get("answer", {}) or {}
        path = row.get("acquisition_path") or []
        evidence = row.get("evidence") or []
        if recipe == "tampered_answer" and isinstance(answer.get("value"), (int, float)) and not isinstance(answer.get("value"), bool):
            return row
        if recipe in {"tampered_evidence", "missing_evidence"} and evidence:
            return row
        if recipe in {"missing_acquisition_path", "invalid_path_action"} and path:
            return row
    return None


def _tamper_answer(sample: dict[str, Any]) -> dict[str, Any]:
    answer = sample.setdefault("task", {}).setdefault("answer", {})
    value = answer.get("value")
    answer["value"] = float(value) + (1.0 if float(value) == 0.0 else abs(float(value)) * 0.5)
    return sample


def _tamper_evidence(sample: dict[str, Any]) -> dict[str, Any]:
    evidence = sample.get("evidence") or []
    if evidence:
        evidence[0]["span_text"] = "tampered evidence that is absent from the source"
    return sample


def _remove_evidence(sample: dict[str, Any]) -> dict[str, Any]:
    sample["evidence"] = []
    return sample


def _remove_path(sample: dict[str, Any]) -> dict[str, Any]:
    sample["acquisition_path"] = []
    return sample


def _tamper_path_action(sample: dict[str, Any]) -> dict[str, Any]:
    path = sample.get("acquisition_path") or []
    if path:
        path[0]["action"] = "not_allowlisted"
    return sample


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text("".join(json.dumps(row, ensure_ascii=True, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def _rate(numerator: int, denominator: int) -> float:
    return round(numerator / denominator, 4) if denominator else 0.0
