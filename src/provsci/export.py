"""Stable ResultCard exports shared by single-document and batch runs."""

from __future__ import annotations

import csv
import json
from collections import Counter
from pathlib import Path
from typing import Any


def write_result_cards(output_path: Path, samples: list[dict[str, Any]], buckets: dict[str, list[dict[str, Any]]]) -> None:
    """Write auditable JSONL cards and a flat CSV view."""
    levels = {sample["id"]: level for level, rows in buckets.items() for sample in rows}
    cards = []
    for sample in samples:
        cards.append({
            "sample_id": sample["id"],
            "source": sample.get("source", {}),
            "result_card": sample.get("result_card", {}),
            "evidence": sample.get("evidence", []),
            "acquisition_path": sample.get("acquisition_path", []),
            "processing": sample.get("processing", {}),
            "verification": sample.get("verification", {}),
            "quality": {**sample.get("quality", {}), "level": levels.get(sample["id"], "silver")},
            "split": sample.get("split"),
        })
    (output_path / "result_cards.jsonl").write_text(
        "".join(json.dumps(card, ensure_ascii=True, sort_keys=True) + "\n" for card in cards),
        encoding="utf-8",
    )
    fields = [
        "sample_id", "doc_id", "domain", "result_type", "entity", "metric", "value", "unit",
        "display", "condition_text", "condition_status", "verification_status", "quality_level",
        "failure_mode", "split",
    ]
    with (output_path / "result_cards.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for sample in samples:
            card = sample.get("result_card", {})
            condition = card.get("condition", {}) or {}
            writer.writerow({
                "sample_id": sample.get("id"),
                "doc_id": sample.get("source", {}).get("doc_id"),
                "domain": card.get("domain"),
                "result_type": card.get("result_type"),
                "entity": card.get("entity"),
                "metric": card.get("metric"),
                "value": card.get("value"),
                "unit": card.get("unit"),
                "display": card.get("display"),
                "condition_text": condition.get("text"),
                "condition_status": condition.get("status"),
                "verification_status": sample.get("verification", {}).get("status"),
                "quality_level": levels.get(sample["id"], "silver"),
                "failure_mode": sample.get("quality", {}).get("failure_mode"),
                "split": sample.get("split"),
            })
    _write_data_card(output_path, samples, buckets, levels)


def _write_data_card(
    output_path: Path,
    samples: list[dict[str, Any]],
    buckets: dict[str, list[dict[str, Any]]],
    levels: dict[str, str],
) -> None:
    """Write a compact dataset card without hiding failed samples."""
    domains = Counter(str((sample.get("result_card", {}) or {}).get("domain", "unspecified")) for sample in samples)
    metrics = Counter(str((sample.get("result_card", {}) or {}).get("metric", "")) for sample in samples)
    modalities = Counter(
        modality
        for sample in samples
        for modality in (sample.get("task", {}).get("classification", {}) or {}).get("modalities", [])
    )
    licenses = Counter(str(sample.get("source", {}).get("license", "")) for sample in samples)
    quality = Counter(levels.get(sample.get("id"), "silver") for sample in samples)
    failures = Counter(
        str(sample.get("quality", {}).get("failure_mode"))
        for sample in samples
        if sample.get("quality", {}).get("failure_mode")
    )
    card = {
        "schema_version": "provsci.data_card.v1",
        "sample_count": len(samples),
        "source_document_count": len({sample.get("source", {}).get("doc_id") for sample in samples}),
        "quality_counts": dict(sorted(quality.items())),
        "domain_counts": dict(sorted(domains.items())),
        "metric_counts": dict(sorted(metrics.items())),
        "modality_counts": dict(sorted(modalities.items())),
        "license_counts": dict(sorted(licenses.items())),
        "failure_mode_counts": dict(sorted(failures.items())),
        "result_card_schema": "result_card.v1",
        "provenance_fields": ["source_hash", "evidence", "acquisition_path", "verification", "quality"],
        "quality_gate": "Gold requires verifier pass, known license and no human-review flag",
        "excluded_from_gold": sorted({level for level in quality if level != "gold"}),
        "bucket_counts": {name: len(rows) for name, rows in buckets.items()},
    }
    (output_path / "data_card.json").write_text(json.dumps(card, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
