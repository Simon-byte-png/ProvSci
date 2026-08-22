"""Runtime contract checks for the provenance-native sample schema.

The JSON Schema remains the public interchange contract. This lightweight
validator keeps the core pipeline dependency-free while catching the fields
that are most dangerous to silently omit before a sample reaches Gold.
"""

from __future__ import annotations

import re
from typing import Any


_SHA256_RE = re.compile(r"^[a-f0-9]{64}$")


def validate_sample_contract(sample: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    _require_keys(sample, ("id", "source", "task", "evidence", "acquisition_path", "processing", "verification", "quality", "split"), "sample", errors)

    source = sample.get("source")
    if not isinstance(source, dict):
        errors.append("source must be an object")
    else:
        _require_keys(source, ("doc_id", "title", "year", "license", "local_path", "page_span", "source_hash"), "source", errors)
        if not isinstance(source.get("year"), int):
            errors.append("source.year must be an integer")
        if not isinstance(source.get("page_span"), list) or not source.get("page_span"):
            errors.append("source.page_span must be a non-empty list")
        if not _SHA256_RE.match(str(source.get("source_hash", ""))):
            errors.append("source.source_hash must be a lowercase SHA-256 hex string")

    task = sample.get("task")
    if not isinstance(task, dict):
        errors.append("task must be an object")
    else:
        _require_keys(task, ("type", "subject", "question", "answer", "classification"), "task", errors)
        answer = task.get("answer")
        if not isinstance(answer, dict):
            errors.append("task.answer must be an object")
        else:
            _require_keys(answer, ("value", "unit", "display"), "task.answer", errors)
        classification = task.get("classification")
        if not isinstance(classification, dict):
            errors.append("task.classification must be an object")
        else:
            _require_keys(classification, ("result_type", "modalities", "task_family", "difficulty", "classifier"), "task.classification", errors)

    if not isinstance(sample.get("evidence"), list) or not sample.get("evidence"):
        errors.append("evidence must be a non-empty list")
    if not isinstance(sample.get("acquisition_path"), list) or not sample.get("acquisition_path"):
        errors.append("acquisition_path must be a non-empty list")

    processing = sample.get("processing")
    if not isinstance(processing, dict):
        errors.append("processing must be an object")
    else:
        _require_keys(processing, ("operations", "raw_value_preserved", "normalization"), "processing", errors)

    verification = sample.get("verification")
    if not isinstance(verification, dict):
        errors.append("verification must be an object")
    else:
        _require_keys(verification, ("status", "tolerance", "evidence_checked"), "verification", errors)
        if verification.get("status") == "pass" and verification.get("evidence_checked") is not True:
            errors.append("a passing sample must have verification.evidence_checked=true")

    quality = sample.get("quality")
    if not isinstance(quality, dict):
        errors.append("quality must be an object")
    else:
        _require_keys(quality, ("needs_human_review", "failure_mode"), "quality", errors)

    if sample.get("split") not in {"train", "dev", "test"}:
        errors.append("split must be train, dev or test")
    return errors


def _require_keys(value: dict[str, Any], keys: tuple[str, ...], prefix: str, errors: list[str]) -> None:
    for key in keys:
        if key not in value:
            errors.append(f"{prefix}.{key} is required")
