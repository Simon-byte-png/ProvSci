"""Deterministic classification and processing annotations for v0 samples."""

from __future__ import annotations

from typing import Any

from .profile import DEFAULT_DOMAIN


def enrich_sample(sample: dict[str, Any]) -> dict[str, Any]:
    """Attach inspectable result labels and processing provenance.

    These rules are intentionally transparent. A model can replace or extend
    them later, but the generated label must remain visible in the sample.
    """
    task = sample.setdefault("task", {})
    task_type = str(task.get("type", "unknown"))
    evidence = sample.get("evidence", [])
    path = sample.get("acquisition_path", [])
    modalities = sorted({str(item.get("modality", "unknown")) for item in evidence})

    if task_type == "numeric_qa":
        result_type = "measurement"
        processing_ops = ["number_unit_parsing"]
        if "table" in modalities:
            processing_ops.insert(0, "table_cell_extraction")
        if "text" in modalities:
            processing_ops.insert(0, "text_span_extraction")
        difficulty = 0.15 + 0.08 * len(path)
        if any(step.get("action") in {"unit_convert", "arith_eval"} for step in path):
            processing_ops.append("derived_value_computation")
            difficulty += 0.15
    elif task_type == "relation":
        result_type = "comparison_relation"
        processing_ops = ["evidence_span_extraction", "relation_normalization"]
        difficulty = 0.45 if task.get("answer", {}).get("subject") and task.get("answer", {}).get("object") else 0.35
    else:
        result_type = "scientific_claim"
        processing_ops = ["evidence_span_extraction"]
        difficulty = 0.5

    task["classification"] = {
        "result_type": result_type,
        "modalities": modalities,
        "task_family": task_type,
        "difficulty": round(min(difficulty, 1.0), 4),
        "classifier": "rules_v0.1",
    }
    answer = task.get("answer", {})
    result_card = sample.setdefault("result_card", {})
    result_card.update({
        "schema_version": "result_card.v1",
        "domain": result_card.get("domain") or sample.get("source", {}).get("domain") or DEFAULT_DOMAIN,
        "result_type": result_type,
        "entity": answer.get("entity") or answer.get("subject") or task.get("subject"),
        "metric": answer.get("metric") or ("relation" if task_type == "relation" else None),
        "value": answer.get("value"),
        "unit": str(answer.get("unit", "")),
        "display": answer.get("display", str(answer.get("value", ""))),
        "condition": result_card.get("condition") or {
            "text": answer.get("condition"),
            "source": "column_header" if answer.get("condition") else "not_extracted",
            "status": "explicit" if answer.get("condition") else "not_extracted",
            "fields": dict(answer.get("condition_fields") or {}),
        },
        "uncertainty": answer.get("uncertainty"),
        "raw_value": answer.get("display", str(answer.get("value", ""))),
        "normalized_value": {
            "value": answer.get("value"),
            "unit": str(answer.get("unit", "")),
        },
    })
    if task_type == "relation":
        result_card["subject"] = answer.get("subject")
        result_card["object"] = answer.get("object")
    sample["processing"] = {
        "operations": processing_ops,
        "raw_value_preserved": True,
        "normalization": "number_unit_v0.1" if task_type == "numeric_qa" else "text_relation_v0.1",
        "raw_value": answer.get("display", str(answer.get("value", ""))),
        "parsed_value": {"value": answer.get("value"), "unit": str(answer.get("unit", ""))},
        "standardized_value": {"value": answer.get("value"), "unit": str(answer.get("unit", ""))},
        "transformations": list(processing_ops),
    }
    if task_type == "numeric_qa" and "text" in modalities:
        answer = task.get("answer", {})
        if answer.get("metric") == "numeric result" or not answer.get("entity"):
            sample.setdefault("quality", {})["needs_human_review"] = True
            sample["quality"]["failure_mode"] = "underspecified_question"
    if task_type == "relation":
        answer = task.get("answer", {})
        subject = str(answer.get("subject", "")).strip()
        object_text = str(answer.get("object", "")).strip()
        leading_noise = ("as shown", "to determine", "to explore", "when ", "compared with", ",", "as the concentration")
        if (
            not subject
            or not object_text
            or subject.casefold().startswith(leading_noise)
            or object_text.casefold().startswith(leading_noise)
            or len(subject.split()) > 20
            or len(object_text.split()) > 24
        ):
            sample.setdefault("quality", {})["needs_human_review"] = True
            sample["quality"]["failure_mode"] = "underspecified_relation"
    return sample
