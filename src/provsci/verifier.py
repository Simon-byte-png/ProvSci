"""Verifier and Gold/Silver gate for generated samples."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .models import DocumentPackage, InputError
from .path import PathExecutionError, PathExecutor
from .values import NumberUnit, convert


VERIFIER_VERSION = "provverify_v0.1"
KNOWN_LICENSES = {
    "CC-BY",
    "CC-BY-4.0",
    "CC-BY-SA",
    "CC-BY-SA-4.0",
    "MIT",
    "public-domain",
}


def is_known_license(value: object) -> bool:
    return str(value or "").strip() in KNOWN_LICENSES


def _numeric_match(actual: Any, expected: dict[str, Any], tolerance: dict[str, Any]) -> bool:
    if isinstance(actual, dict) and "value" in actual:
        actual_value = NumberUnit(float(actual["value"]), str(actual.get("unit", "")))
    elif isinstance(actual, (int, float)) and not isinstance(actual, bool):
        actual_value = NumberUnit(float(actual), "")
    else:
        return False
    expected_value = NumberUnit(float(expected["value"]), str(expected.get("unit", "")))
    if actual_value.unit != expected_value.unit:
        if not actual_value.unit or not expected_value.unit:
            return False
        try:
            actual_value = convert(actual_value, expected_value.unit)
        except ValueError:
            return False
    delta = abs(actual_value.value - expected_value.value)
    abs_tol = tolerance.get("abs")
    rel_tol = tolerance.get("rel")
    allowed = float(abs_tol) if abs_tol is not None else 0.0
    if rel_tol is not None:
        allowed = max(allowed, abs(float(expected_value.value)) * float(rel_tol))
    return delta <= allowed


def _answer_match(actual: Any, expected: dict[str, Any], tolerance: dict[str, Any], task_type: str) -> bool:
    if task_type in {"numeric_qa", "table_lookup"}:
        return _numeric_match(actual, expected, tolerance)
    expected_value = str(expected.get("value", expected.get("display", ""))).strip().casefold()
    if isinstance(actual, dict):
        actual_value = str(actual.get("value", actual.get("display", ""))).strip().casefold()
    else:
        actual_value = str(actual).strip().casefold()
    if not expected_value or actual_value != expected_value:
        return False
    if task_type == "relation" and isinstance(actual, dict):
        for field in ("subject", "object"):
            if field in expected and str(actual.get(field, "")).strip().casefold() != str(expected[field]).strip().casefold():
                return False
    return True


def verify_sample(sample: dict[str, Any], document: DocumentPackage) -> dict[str, Any]:
    """Execute a sample path and attach an auditable verification record."""
    checked_at = datetime.now(timezone.utc).isoformat()
    verification = sample.setdefault("verification", {})
    verification.update({
        "status": "unknown",
        "recomputed": None,
        "verifier_version": VERIFIER_VERSION,
        "checked_at": checked_at,
    })
    quality = sample.setdefault("quality", {})
    quality["failure_mode"] = None
    quality["needs_human_review"] = False

    if not sample.get("evidence"):
        return _fail(sample, "missing_evidence")
    evidence_error = _check_evidence(sample["evidence"], document)
    if evidence_error:
        return _fail(sample, evidence_error)
    path = sample.get("acquisition_path")
    if not path:
        return _fail(sample, "missing_acquisition_path")

    try:
        recomputed, trace = PathExecutor(document).execute(path)
    except PathExecutionError as exc:
        sample["verification"]["error"] = str(exc)
        return _fail(sample, "path_execution_error")

    answer = sample.get("task", {}).get("answer", {})
    tolerance = sample["verification"].get("tolerance") or {"rel": 0.02, "abs": None}
    task_type = str(sample.get("task", {}).get("type", ""))
    matches = _answer_match(recomputed, answer, tolerance, task_type)
    sample["verification"]["recomputed"] = recomputed
    sample["verification"]["trace"] = trace
    sample["verification"]["evidence_checked"] = True
    if not matches:
        return _fail(sample, "answer_mismatch")
    sample["verification"]["status"] = "pass"
    return sample


def curate_bucket(sample: dict[str, Any]) -> str:
    """Apply the conservative v0 Gold gate after deterministic verification."""
    license_name = str(sample.get("source", {}).get("license", "")).strip()
    if (
        sample.get("verification", {}).get("status") == "pass"
        and is_known_license(license_name)
        and not sample.get("quality", {}).get("needs_human_review", False)
    ):
        return "gold"
    return "silver"


def _fail(sample: dict[str, Any], failure_mode: str) -> dict[str, Any]:
    sample["verification"]["status"] = "fail"
    sample.setdefault("quality", {})["failure_mode"] = failure_mode
    sample["quality"]["needs_human_review"] = True
    return sample


def _check_evidence(evidence: list[dict[str, Any]], document: DocumentPackage) -> str | None:
    """Resolve every evidence locator before a path can pass."""
    for item in evidence:
        modality = str(item.get("modality", ""))
        locator = item.get("locator") or {}
        span_text = str(item.get("span_text", ""))
        try:
            if modality == "table":
                table = document.table(str(locator["table_id"]))
                if "page" in locator and int(locator["page"]) != int(table.get("page", locator["page"])):
                    return "evidence_mismatch"
                row_key = str(locator["row"])
                col = str(locator["col"])
                rows = table.get("rows", [])
                if "row_index" in locator:
                    row_index = int(locator["row_index"])
                    row = rows[row_index] if 0 <= row_index < len(rows) else None
                else:
                    labels = [next((row.get(key) for key in ("Sample", "sample", "Cell line", "cell line", "cell_line", "Compound", "compound", "Name", "name", "id") if row.get(key) not in (None, "")), None) for row in rows]
                    row = next((row for row, label in zip(rows, labels) if str(label) == row_key), None)
                if row is None or col not in row or str(row[col]).strip() != span_text.strip():
                    return "evidence_mismatch"
            elif modality == "text":
                paragraph = document.paragraph(str(locator["paragraph_id"]))
                if "page" in locator and int(locator["page"]) != int(paragraph.get("page", locator["page"])):
                    return "evidence_mismatch"
                if span_text.strip() not in str(paragraph.get("text", "")):
                    return "evidence_mismatch"
            elif modality == "figure":
                figure = document.figure(str(locator["figure_id"]))
                if span_text.strip() not in str(figure.get("alt_text", "")):
                    return "evidence_mismatch"
            else:
                return "unsupported_evidence_modality"
        except (KeyError, InputError):
            return "evidence_not_found"
    return None
