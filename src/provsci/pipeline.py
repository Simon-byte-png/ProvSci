"""End-to-end v0 pipeline and JSONL artifact writer."""

from __future__ import annotations

import json
import hashlib
from collections import Counter
from pathlib import Path
from typing import Any

from .adapters import load_document
from .batch import mine_candidates
from .classify import enrich_sample
from .contract import validate_sample_contract
from .models import DocumentPackage
from .verifier import curate_bucket, verify_sample


def run_pipeline(input_path: str | Path, output_dir: str | Path, strategy: str = "result_focused") -> dict[str, Any]:
    input_file = Path(input_path)
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    document = load_document(input_file)
    source_hash = hashlib.sha256(input_file.read_bytes()).hexdigest()

    samples: list[dict[str, Any]] = []
    for candidate in mine_candidates(document, strategy):
        sample = candidate.to_sample(document.license, document.title, document.local_path)
        sample["source"]["year"] = document.year
        sample["source"]["source_hash"] = source_hash
        for key in ("source_url", "retrieved_at", "license_source", "adapter"):
            if key in document.metadata:
                sample["source"][key] = document.metadata[key]
        sample = enrich_sample(verify_sample(sample, document))
        contract_errors = validate_sample_contract(sample)
        if contract_errors:
            sample["verification"]["status"] = "fail"
            sample["quality"]["needs_human_review"] = True
            sample["quality"]["failure_mode"] = "schema_contract_error"
            sample["verification"]["contract_errors"] = contract_errors
        samples.append(sample)

    buckets = {"gold": [], "silver": []}
    seen_ids: set[str] = set()
    failures = Counter()
    for sample in samples:
        if sample["id"] in seen_ids:
            sample["verification"]["status"] = "fail"
            sample["quality"]["failure_mode"] = "duplicate_sample"
            sample["quality"]["needs_human_review"] = True
        seen_ids.add(sample["id"])
        bucket = curate_bucket(sample)
        buckets[bucket].append(sample)
        failure_mode = sample.get("quality", {}).get("failure_mode")
        if failure_mode:
            failures[failure_mode] += 1

    _write_jsonl(output_path / "all.jsonl", samples)
    _write_jsonl(output_path / "gold.jsonl", buckets["gold"])
    _write_jsonl(output_path / "silver.jsonl", buckets["silver"])
    _write_jsonl(
        output_path / "human_review.jsonl",
        [sample for sample in samples if sample.get("quality", {}).get("needs_human_review")],
    )
    summary = {
        "doc_id": document.doc_id,
        "input": str(input_file),
        "total_candidates": len(samples),
        "gold": len(buckets["gold"]),
        "silver": len(buckets["silver"]),
        "human_review": sum(sample.get("quality", {}).get("needs_human_review", False) for sample in samples),
        "path_reproducibility": _rate(
            sum(sample.get("verification", {}).get("status") == "pass" for sample in samples), len(samples)
        ),
        "failure_modes": dict(failures),
        "verifier_version": "provverify_v0.1",
        "strategy": strategy,
    }
    (output_path / "summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    return summary


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=True, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


def _rate(numerator: int, denominator: int) -> float:
    return round(numerator / denominator, 4) if denominator else 0.0
