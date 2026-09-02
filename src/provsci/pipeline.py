"""End-to-end v0 pipeline and JSONL artifact writer."""

from __future__ import annotations

import json
import hashlib
import time
from collections import Counter
from pathlib import Path
from typing import Any

from .adapters import load_document
from .batch import mine_candidates
from .classify import enrich_sample
from .contract import validate_sample_contract
from .dedupe import annotate_duplicate_groups
from .export import write_result_cards
from .sources import source_record, source_record_errors
from .models import DocumentPackage
from .verifier import curate_bucket, verify_sample


def run_pipeline(
    input_path: str | Path,
    output_dir: str | Path,
    strategy: str = "result_focused",
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    started = time.perf_counter()
    input_file = Path(input_path)
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    document = load_document(input_file, metadata)
    source_hash = hashlib.sha256(input_file.read_bytes()).hexdigest()
    source_info = source_record(input_file, document, source_hash)

    samples: list[dict[str, Any]] = []
    for candidate in mine_candidates(document, strategy):
        sample = candidate.to_sample(document.license, document.title, document.local_path)
        sample["source"]["year"] = document.year
        sample["source"]["source_hash"] = source_hash
        sample["source"].update({key: value for key, value in source_info.items() if key not in {"doc_id", "title", "year", "license", "local_path", "source_hash"}})
        for key in ("source_url", "retrieved_at", "license_source", "adapter", "domain", "source_version", "retrieval_method", "doi", "pmid"):
            if key in document.metadata:
                sample["source"][key] = document.metadata[key]
        if document.metadata.get("domain"):
            sample.setdefault("result_card", {})["domain"] = document.metadata["domain"]
        sample = enrich_sample(verify_sample(sample, document))
        contract_errors = validate_sample_contract(sample)
        if contract_errors:
            sample["verification"]["status"] = "fail"
            sample["quality"]["needs_human_review"] = True
            sample["quality"]["failure_mode"] = "schema_contract_error"
            sample["verification"]["contract_errors"] = contract_errors
        samples.append(sample)

    duplicate_stats = annotate_duplicate_groups(samples)
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
    from .review import build_review_queue
    review_queue = build_review_queue(output_path)
    write_result_cards(output_path, samples, buckets)
    summary = {
        "doc_id": document.doc_id,
        "input": str(input_file),
        "total_candidates": len(samples),
        "gold": len(buckets["gold"]),
        "silver": len(buckets["silver"]),
        "human_review": sum(sample.get("quality", {}).get("needs_human_review", False) for sample in samples),
        "review_queue": len(review_queue),
        "path_reproducibility": _rate(
            sum(sample.get("verification", {}).get("status") == "pass" for sample in samples), len(samples)
        ),
        "failure_modes": dict(failures),
        **duplicate_stats,
        "verifier_version": "provverify_v0.1",
        "strategy": strategy,
        "source": source_info,
        "source_record_errors": source_record_errors(source_info),
    }
    runtime_seconds = round(time.perf_counter() - started, 6)
    summary.update({
        "runtime_seconds": runtime_seconds,
        "candidate_rate_per_second": round(len(samples) / runtime_seconds, 4) if runtime_seconds else 0.0,
        "estimated_cost_usd": 0.0,
        "cost_basis": "deterministic_local_no_model_calls",
    })
    (output_path / "summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    return summary


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=True, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )




def _rate(numerator: int, denominator: int) -> float:
    return round(numerator / denominator, 4) if denominator else 0.0
