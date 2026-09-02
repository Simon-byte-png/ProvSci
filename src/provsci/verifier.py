"""Verifier and Gold/Silver gate for generated samples."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .models import DocumentPackage, InputError
from .path import PathExecutionError, PathExecutor
from .figures import figure_axis, point_display, resolve_figure_point
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

    if not _path_evidence_aligned(path, trace, sample["evidence"]):
        sample["verification"]["recomputed"] = recomputed
        sample["verification"]["trace"] = trace
        sample["verification"]["evidence_checked"] = True
        return _fail(sample, "evidence_mismatch")

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
    if not is_known_license(sample.get("source", {}).get("license")):
        # The claim itself replayed, but its provenance cannot be publicly
        # redistributed until a human confirms the source licence.
        sample["quality"]["failure_mode"] = "license_unknown"
        sample["quality"]["needs_human_review"] = True
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
                    labels = [next((row.get(key) for key in (
                        "Sample", "sample", "Sample ID", "sample_id", "Cell line", "cell line", "cell_line",
                        "Compound", "compound", "Batch", "batch", "Group", "group", "Specimen", "specimen",
                        "Material", "material", "Treatment", "treatment", "Condition", "condition",
                        "Name", "name", "Analyte", "analyte", "hPMTs", "hPMT", "PTM", "ptm", "id",
                    ) if row.get(key) not in (None, "")), None) for row in rows]
                    row = next((row for row, label in zip(rows, labels) if str(label) == row_key), None)
                if row is None or col not in row or str(row[col]).strip() != span_text.strip():
                    return "evidence_mismatch"
            elif modality == "text":
                paragraph = document.paragraph(str(locator["paragraph_id"]))
                if "page" in locator and int(locator["page"]) != int(paragraph.get("page", locator["page"])):
                    return "evidence_mismatch"
                if not _span_matches(str(paragraph.get("text", "")), span_text, locator):
                    return "evidence_mismatch"
            elif modality == "figure":
                figure = document.figure(str(locator["figure_id"]))
                if "point_index" in locator:
                    try:
                        point = resolve_figure_point(
                            figure,
                            series_index=int(locator.get("series_index", 0)),
                            point_index=int(locator["point_index"]),
                        )
                    except (KeyError, TypeError, ValueError):
                        return "evidence_not_found"
                    if str(locator.get("series", "")) and str(locator.get("series")) != str(point.get("series_name", "")):
                        return "evidence_mismatch"
                    if point_display(point, figure_axis(figure, "y")).strip() != span_text.strip():
                        return "evidence_mismatch"
                elif not _span_matches(str(figure.get("alt_text", "")), span_text, locator):
                    return "evidence_mismatch"
            elif modality == "supplement":
                supplement = document.supplement(str(locator["supplement_id"]))
                if not _span_matches(str(supplement.get("text", "")), span_text, locator):
                    return "evidence_mismatch"
            else:
                return "unsupported_evidence_modality"
        except (KeyError, InputError):
            return "evidence_not_found"
    return None


def _span_matches(source_text: str, span_text: str, locator: dict[str, Any]) -> bool:
    """Validate a locator's character span when one is supplied.

    A fallback substring check is retained for legacy evidence without
    offsets, but newly mined text/figure/supplement evidence always carries a
    ``char_span``.  Comparing the exact slice prevents a repeated number in a
    paragraph from masquerading as the claimed evidence.
    """
    expected = str(span_text).strip()
    if not expected:
        return False
    raw_span = locator.get("char_span")
    if raw_span is None:
        return expected in source_text
    if not isinstance(raw_span, (list, tuple)) or len(raw_span) != 2:
        return False
    try:
        start, end = int(raw_span[0]), int(raw_span[1])
    except (TypeError, ValueError):
        return False
    if start < 0 or end < start or end > len(source_text):
        return False
    return source_text[start:end].strip() == expected


def _path_evidence_aligned(
    path: list[dict[str, Any]],
    trace: list[dict[str, Any]],
    evidence: list[dict[str, Any]],
) -> bool:
    """Ensure the executable path reads the same locator shown as evidence."""
    if not evidence:
        return False
    item = evidence[0] if isinstance(evidence[0], dict) else {}
    modality = str(item.get("modality", ""))
    locator = item.get("locator") or {}
    if not path or not trace:
        return False
    first = path[0] if isinstance(path[0], dict) else {}
    args = first.get("args") or {}
    action = str(first.get("action", ""))
    if modality == "table":
        if action != "extract_table_cell":
            return False
        for key in ("table_id", "col"):
            if str(args.get(key, "")) != str(locator.get(key, "")):
                return False
        # ``row_index`` is the unambiguous locator when available.  Legacy
        # paths may only carry a row label, so compare whichever form exists.
        if "row_index" in locator and "row_index" in args:
            return int(args["row_index"]) == int(locator["row_index"])
        return str(args.get("row_key", "")) == str(locator.get("row", ""))
    if modality == "text" and action != "read_text_span":
        return False
    if modality == "figure":
        if "point_index" in locator:
            if action != "extract_figure_point":
                return False
            for key in ("figure_id", "series_index", "point_index"):
                if str(args.get(key, "")) != str(locator.get(key, "")):
                    return False
            return True
        if action != "read_figure_alt_text":
            return False
    if modality == "supplement" and action != "read_supplement_text":
        return False
    if modality not in {"text", "figure", "supplement"}:
        return False
    expected_span = locator.get("char_span")
    if expected_span is None:
        return True
    # The extraction step, rather than the initial read step, owns the exact
    # character offsets.  Compare every trace output carrying a span so paths
    # ending in unit conversion or arithmetic remain covered.
    for step in trace:
        output = step.get("output")
        if isinstance(output, dict) and "char_span" in output:
            return list(output.get("char_span")) == list(expected_span)
    # A path that claims a character span but never extracts one cannot prove
    # that its answer came from that span.
    return False
