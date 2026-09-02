"""Batch execution with deterministic document-level split assignment."""

from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Any, Iterable

from .adapters import load_document
from .classify import enrich_sample
from .contract import validate_sample_contract
from .dedupe import annotate_duplicate_groups
from .export import write_result_cards
from .sources import source_record, source_record_errors
from .verifier import curate_bucket, is_known_license, verify_sample


def assign_split(doc_id: str, train: int = 80, dev: int = 10) -> str:
    """Assign a document to one split; all samples from a document follow it."""
    bucket = int(hashlib.sha256(doc_id.encode("utf-8")).hexdigest()[:8], 16) % 100
    if bucket < train:
        return "train"
    if bucket < train + dev:
        return "dev"
    return "test"


def mine_candidates(document: Any, strategy: str = "result_focused") -> list[Any]:
    """Select candidate sources for an architecture variant."""
    if strategy not in {"table_only", "full", "result_focused", "multimodal"}:
        raise ValueError(f"unknown mining strategy: {strategy}")
    from .miner import is_core_result_candidate, is_result_paragraph, mine_figure_numeric_candidates, mine_numeric_table_candidates, mine_numeric_text_candidates, mine_supplement_numeric_candidates, mine_text_relations

    candidates = list(mine_numeric_table_candidates(document))
    if strategy == "result_focused":
        result_tables = [
            table for table in document.tables
            if not table.get("section_path")
            or any("result" in str(section).casefold() or "efficacy" in str(section).casefold() for section in table.get("section_path", []))
        ]
        if len(result_tables) != len(document.tables):
            from .models import DocumentPackage
            result_doc = DocumentPackage(
                doc_id=document.doc_id,
                title=document.title,
                year=document.year,
                license=document.license,
                local_path=document.local_path,
                paragraphs=document.paragraphs,
                tables=result_tables,
                figures=document.figures,
                supplements=document.supplements,
                metadata=document.metadata,
            )
            candidates = list(mine_numeric_table_candidates(result_doc))
    if strategy in {"full", "result_focused", "multimodal"}:
        if strategy == "result_focused":
            from .models import DocumentPackage
            document = DocumentPackage(
                doc_id=document.doc_id,
                title=document.title,
                year=document.year,
                license=document.license,
                local_path=document.local_path,
                paragraphs=[paragraph for paragraph in document.paragraphs if is_result_paragraph(paragraph)],
                tables=document.tables,
                metadata=document.metadata,
                supplements=document.supplements,
            )
        candidates.extend(mine_numeric_text_candidates(document))
        candidates.extend(mine_text_relations(document))
        candidates.extend(mine_supplement_numeric_candidates(document))
        if strategy == "multimodal":
            candidates.extend(mine_figure_numeric_candidates(document))
        if strategy == "result_focused":
            candidates = [candidate for candidate in candidates if is_core_result_candidate(candidate)]
    return candidates


def run_batch(
    input_paths: Iterable[str | Path | tuple[str | Path, dict[str, Any]]],
    output_dir: str | Path,
    strategy: str = "result_focused",
) -> dict[str, Any]:
    started = time.perf_counter()
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    all_samples: list[dict[str, Any]] = []
    documents: list[dict[str, Any]] = []
    for index, input_item in enumerate(input_paths, 1):
        if isinstance(input_item, tuple):
            input_path, metadata = input_item
        else:
            input_path, metadata = input_item, None
        document = load_document(input_path, metadata)
        source_hash = hashlib.sha256(Path(input_path).read_bytes()).hexdigest()
        source_info = source_record(input_path, document, source_hash)
        split = assign_split(document.doc_id)
        samples = []
        candidates = mine_candidates(document, strategy)
        for candidate in candidates:
            sample = candidate.to_sample(document.license, document.title, document.local_path)
            sample["source"]["year"] = document.year
            sample["source"]["source_hash"] = source_hash
            sample["source"].update({key: value for key, value in source_info.items() if key not in {"doc_id", "title", "year", "license", "local_path", "source_hash"}})
            for key in ("source_url", "retrieved_at", "license_source", "adapter", "domain", "source_version", "retrieval_method", "doi", "pmid"):
                if key in document.metadata:
                    sample["source"][key] = document.metadata[key]
            if document.metadata.get("domain"):
                sample.setdefault("result_card", {})["domain"] = document.metadata["domain"]
            sample["split"] = split
            sample = enrich_sample(verify_sample(sample, document))
            contract_errors = validate_sample_contract(sample)
            if contract_errors:
                sample["verification"]["status"] = "fail"
                sample["quality"]["needs_human_review"] = True
                sample["quality"]["failure_mode"] = "schema_contract_error"
                sample["verification"]["contract_errors"] = contract_errors
            samples.append(sample)
        all_samples.extend(samples)
        documents.append({
            "doc_id": document.doc_id,
            "input": str(input_path),
            "split": split,
            "candidates": len(samples),
            "gold": 0,
            "silver": 0,
            "source": source_info,
            "source_record_errors": source_record_errors(source_info),
        })

    seen_ids: set[str] = set()
    for sample in all_samples:
        if sample["id"] in seen_ids:
            sample["verification"]["status"] = "fail"
            sample["quality"]["failure_mode"] = "duplicate_sample"
            sample["quality"]["needs_human_review"] = True
        seen_ids.add(sample["id"])

    duplicate_stats = annotate_duplicate_groups(all_samples)

    gold = [sample for sample in all_samples if curate_bucket(sample) == "gold"]
    silver = [sample for sample in all_samples if curate_bucket(sample) == "silver"]
    counts_by_doc: dict[str, dict[str, int]] = {}
    for sample in all_samples:
        doc_counts = counts_by_doc.setdefault(sample["source"]["doc_id"], {"gold": 0, "silver": 0})
        doc_counts[curate_bucket(sample)] += 1
    for document in documents:
        counts = counts_by_doc.get(document["doc_id"], {"gold": 0, "silver": 0})
        document.update(counts)
    _write_jsonl(output / "all.jsonl", all_samples)
    _write_jsonl(output / "gold.jsonl", gold)
    _write_jsonl(output / "silver.jsonl", silver)
    _write_jsonl(
        output / "human_review.jsonl",
        [sample for sample in all_samples if sample.get("quality", {}).get("needs_human_review")],
    )
    from .review import build_review_queue
    review_queue = build_review_queue(output)
    write_result_cards(output, all_samples, {"gold": gold, "silver": silver})
    summary = {
        "documents": documents,
        "document_count": len(documents),
        "total_candidates": len(all_samples),
        "gold": len(gold),
        "silver": len(silver),
        "human_review": sum(sample.get("quality", {}).get("needs_human_review", False) for sample in all_samples),
        "review_queue": len(review_queue),
        "path_reproducibility": _rate(sum(s["verification"]["status"] == "pass" for s in all_samples), len(all_samples)),
        "split_doc_ids": {split: sorted({d["doc_id"] for d in documents if d["split"] == split}) for split in ("train", "dev", "test")},
        "split_sample_counts": {split: sum(s.get("split") == split for s in all_samples) for split in ("train", "dev", "test")},
        "duplicate_sample_ids": _duplicates([sample["id"] for sample in all_samples]),
        **duplicate_stats,
        "evidence_coverage": _rate(sum(bool(s.get("evidence")) for s in all_samples), len(all_samples)),
        "license_coverage": _rate(sum(is_known_license(s.get("source", {}).get("license")) for s in all_samples), len(all_samples)),
        "strategy": strategy,
    }
    runtime_seconds = round(time.perf_counter() - started, 6)
    summary.update({
        "runtime_seconds": runtime_seconds,
        "candidate_rate_per_second": round(len(all_samples) / runtime_seconds, 4) if runtime_seconds else 0.0,
        "estimated_cost_usd": 0.0,
        "cost_basis": "deterministic_local_no_model_calls",
    })
    (output / "summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    return summary


def read_manifest(manifest_path: str | Path) -> list[Path]:
    manifest = Path(manifest_path)
    raw = json.loads(manifest.read_text(encoding="utf-8"))
    root = manifest.parent
    paths = raw.get("documents", raw) if isinstance(raw, dict) else raw
    if not isinstance(paths, list):
        raise ValueError("manifest must contain a documents list")
    return [
        Path(item["path"] if isinstance(item, dict) else item)
        if Path(item["path"] if isinstance(item, dict) else item).is_absolute()
        else root / (item["path"] if isinstance(item, dict) else item)
        for item in paths
    ]


def read_manifest_entries(manifest_path: str | Path) -> list[tuple[Path, dict[str, Any]]]:
    manifest = Path(manifest_path)
    raw = json.loads(manifest.read_text(encoding="utf-8"))
    entries = raw.get("documents", []) if isinstance(raw, dict) else raw
    if not isinstance(entries, list):
        raise ValueError("manifest must contain a documents list")
    result = []
    for item in entries:
        relative = item["path"] if isinstance(item, dict) else item
        path = Path(relative)
        if not path.is_absolute():
            path = manifest.parent / path
        metadata = dict(item.get("metadata", {})) if isinstance(item, dict) else {}
        result.append((path, metadata))
    return result


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text("".join(json.dumps(row, ensure_ascii=True, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def _duplicates(values: list[str]) -> list[str]:
    seen: set[str] = set()
    duplicates: set[str] = set()
    for value in values:
        if value in seen:
            duplicates.add(value)
        seen.add(value)
    return sorted(duplicates)


def _rate(numerator: int, denominator: int) -> float:
    return round(numerator / denominator, 4) if denominator else 0.0
