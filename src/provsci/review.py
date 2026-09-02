"""Append-only human-review decisions and materialized run artifacts."""

from __future__ import annotations

import copy
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .adapters import load_document
from .classify import enrich_sample
from .contract import validate_sample_contract
from .dedupe import annotate_duplicate_groups
from .export import write_result_cards
from .verifier import curate_bucket, verify_sample


DECISIONS = {"accept", "modify", "reject"}

# Larger values are reviewed first.  These are operational priorities, not
# scientific confidence scores and must never be presented as a model score.
REVIEW_PRIORITY = {
    "conflicting_values": 100,
    "evidence_mismatch": 95,
    "evidence_not_found": 95,
    "missing_evidence": 90,
    "path_execution_error": 90,
    "answer_mismatch": 85,
    "missing_acquisition_path": 80,
    "schema_contract_error": 75,
    "license_unknown": 60,
    "underspecified_relation": 50,
    "underspecified_question": 45,
    "duplicate_sample": 40,
}


def build_review_queue(
    run_dir: str | Path,
    output_path: str | Path | None = None,
) -> list[dict[str, Any]]:
    """Build a deterministic, reviewable queue from a completed run.

    The queue is a derived view: it never changes ``all.jsonl`` or the
    append-only decision log.  Ties are resolved by document and sample ID so
    repeated invocations produce the same order.  Samples already rejected by
    a reviewer are omitted from the active queue.
    """
    run = Path(run_dir)
    source = run / "human_review.jsonl"
    if not source.exists():
        raise ReviewError(f"human review queue not found: {source}")
    rows = _read_jsonl(source)
    queue: list[dict[str, Any]] = []
    for row in rows:
        quality = row.get("quality", {}) or {}
        if quality.get("review_disposition") == "rejected":
            continue
        failure_mode = str(quality.get("failure_mode") or "unclassified")
        priority = int(REVIEW_PRIORITY.get(failure_mode, 30))
        evidence = row.get("evidence", []) or []
        queue.append({
            "sample_id": row.get("id"),
            "doc_id": (row.get("source", {}) or {}).get("doc_id"),
            "question": (row.get("task", {}) or {}).get("question"),
            "failure_mode": failure_mode,
            "priority": priority,
            "recommended_action": _recommended_action(failure_mode),
            "source": {
                "title": (row.get("source", {}) or {}).get("title"),
                "year": (row.get("source", {}) or {}).get("year"),
                "license": (row.get("source", {}) or {}).get("license"),
                "source_hash": (row.get("source", {}) or {}).get("source_hash"),
                "local_path": (row.get("source", {}) or {}).get("local_path"),
                "source_url": (row.get("source", {}) or {}).get("source_url"),
            },
            # Keep the review view self-contained.  These fields are copied
            # from the active sample so a UI consumer never has to read the
            # run directory or silently reconstruct a ResultCard.
            "task": copy.deepcopy(row.get("task", {}) or {}),
            "result_card": copy.deepcopy(row.get("result_card", {}) or {}),
            "acquisition_path": copy.deepcopy(row.get("acquisition_path", []) or []),
            "evidence": copy.deepcopy(evidence),
            "verification": copy.deepcopy(row.get("verification", {}) or {}),
            "quality": copy.deepcopy(quality),
        })
    queue.sort(key=lambda item: (-item["priority"], str(item.get("doc_id", "")), str(item.get("sample_id", ""))))
    for index, item in enumerate(queue, 1):
        item["rank"] = index
    destination = Path(output_path) if output_path is not None else run / "review_queue.jsonl"
    _write_jsonl(destination, queue)
    return queue


def _recommended_action(failure_mode: str) -> str:
    if failure_mode in {"evidence_mismatch", "evidence_not_found", "missing_evidence"}:
        return "locate_or_confirm_source_evidence"
    if failure_mode in {"path_execution_error", "missing_acquisition_path", "answer_mismatch"}:
        return "inspect_path_and_replay"
    if failure_mode == "license_unknown":
        return "confirm_source_license_before_export"
    if failure_mode in {"conflicting_values", "underspecified_relation", "underspecified_question"}:
        return "resolve_semantic_ambiguity"
    if failure_mode == "duplicate_sample":
        return "compare_duplicate_provenance"
    return "inspect_sample_and_decide"


class ReviewError(ValueError):
    """Raised when a review decision cannot be safely applied."""


def record_review_decision(
    run_dir: str | Path,
    sample_id: str,
    decision: str,
    reviewer: str,
    *,
    comment: str = "",
    changes: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Append one decision and rebuild the run's curation artifacts.

    Decisions are append-only.  The current sample is materialized in
    ``all.jsonl`` while ``review_decisions.jsonl`` preserves the before/after
    audit record.  A human decision can relax a semantic review flag, but it
    can never bypass deterministic path verification or an unknown license.
    ``modify`` changes are dotted object paths (for example,
    ``task.answer.value``) and are re-verified against the original document.
    """
    output = Path(run_dir)
    all_path = output / "all.jsonl"
    if not all_path.exists():
        raise ReviewError(f"run results not found: {all_path}")
    normalized_decision = str(decision).strip().casefold()
    if normalized_decision not in DECISIONS:
        raise ReviewError(f"decision must be one of {sorted(DECISIONS)}")
    normalized_reviewer = str(reviewer).strip()
    if not normalized_reviewer:
        raise ReviewError("reviewer cannot be empty")
    if changes is not None and not isinstance(changes, dict):
        raise ReviewError("changes must be an object of dotted paths to values")
    if normalized_decision == "modify" and not changes:
        raise ReviewError("modify requires at least one change")
    if normalized_decision != "modify" and changes:
        raise ReviewError("changes are only allowed with modify")

    samples = _read_jsonl(all_path)
    index = next((i for i, row in enumerate(samples) if row.get("id") == sample_id), None)
    if index is None:
        raise ReviewError(f"sample not found: {sample_id}")
    before = copy.deepcopy(samples[index])
    sample = copy.deepcopy(before)
    if normalized_decision == "modify":
        _apply_changes(sample, changes or {})
        _reverify_modified_sample(sample, output)
    elif normalized_decision == "accept":
        _accept_sample(sample)
    else:
        _reject_sample(sample)
    sample.setdefault("quality", {})["review_decision"] = normalized_decision
    sample["quality"]["reviewer"] = normalized_reviewer
    sample["quality"]["review_comment"] = str(comment or "")
    samples[index] = sample

    decision_record = {
        "decision_id": _decision_id(output, sample_id, normalized_reviewer),
        "sample_id": sample_id,
        "decision": normalized_decision,
        "reviewer": normalized_reviewer,
        "comment": str(comment or ""),
        "changes": copy.deepcopy(changes or {}),
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "before": _review_snapshot(before),
        "after": _review_snapshot(sample),
    }
    _append_jsonl(output / "review_decisions.jsonl", decision_record)
    _materialize(output, samples)
    return decision_record


def _reverify_modified_sample(sample: dict[str, Any], run_dir: Path) -> None:
    """Re-run the deterministic verifier after a human field edit."""
    source_path = _source_input_path(run_dir, sample.get("source", {}).get("doc_id"))
    if source_path is None:
        sample.setdefault("quality", {})["needs_human_review"] = True
        sample["quality"]["failure_mode"] = "review_revalidation_unavailable"
        return
    try:
        source_metadata = {
            key: value
            for key, value in (sample.get("source", {}) or {}).items()
            if key in {"doc_id", "title", "year", "license", "local_path", "domain", "source_url", "doi", "pmid"}
        }
        document = load_document(source_path, source_metadata)
        verify_sample(sample, document)
        enrich_sample(sample)
        contract_errors = validate_sample_contract(sample)
        if contract_errors:
            sample.setdefault("verification", {})["status"] = "fail"
            sample.setdefault("quality", {})["needs_human_review"] = True
            sample["quality"]["failure_mode"] = "schema_contract_error"
            sample["verification"]["contract_errors"] = contract_errors
    except Exception as exc:  # pragma: no cover - protects an interactive queue
        sample.setdefault("verification", {})["status"] = "fail"
        sample.setdefault("verification", {})["error"] = str(exc)
        sample.setdefault("quality", {})["needs_human_review"] = True
        sample["quality"]["failure_mode"] = "review_revalidation_error"


def _accept_sample(sample: dict[str, Any]) -> None:
    quality = sample.setdefault("quality", {})
    quality["needs_human_review"] = False
    if sample.get("verification", {}).get("status") != "pass":
        # Human acceptance is not a verifier bypass.  Keep the sample Silver
        # and make the remaining blocker explicit in the audit record.
        quality["failure_mode"] = "human_accept_unverified"
    elif quality.get("failure_mode") not in {"license_unknown"}:
        quality["failure_mode"] = None


def _reject_sample(sample: dict[str, Any]) -> None:
    quality = sample.setdefault("quality", {})
    quality["needs_human_review"] = False
    quality["failure_mode"] = "human_rejected"
    quality["review_disposition"] = "rejected"


def _apply_changes(sample: dict[str, Any], changes: dict[str, Any]) -> None:
    immutable_prefixes = ("id", "source.doc_id", "source.source_hash", "source.local_path")
    for dotted_path, value in changes.items():
        path = str(dotted_path).strip()
        if not path or path in immutable_prefixes or any(path.startswith(prefix + ".") for prefix in immutable_prefixes):
            raise ReviewError(f"cannot modify immutable provenance field: {path}")
        parts = path.split(".")
        target: Any = sample
        for part in parts[:-1]:
            if not isinstance(target, dict):
                raise ReviewError(f"change path traverses a non-object: {path}")
            if part not in target:
                target[part] = {}
            target = target[part]
        if not isinstance(target, dict):
            raise ReviewError(f"change path does not point to an object field: {path}")
        target[parts[-1]] = copy.deepcopy(value)


def _source_input_path(run_dir: Path, doc_id: Any) -> Path | None:
    summary_path = run_dir / "summary.json"
    if not summary_path.exists():
        return None
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    candidates: list[Any] = []
    if isinstance(summary.get("input"), str):
        candidates.append(summary["input"])
    for entry in summary.get("documents", []):
        if entry.get("doc_id") == doc_id:
            candidates.append(entry.get("input"))
    for raw in candidates:
        if not raw:
            continue
        path = Path(str(raw))
        if path.exists():
            return path
        if not path.is_absolute():
            for base in (run_dir, run_dir.parent, Path.cwd()):
                candidate = base / path
                if candidate.exists():
                    return candidate
    return None


def _materialize(output: Path, samples: list[dict[str, Any]]) -> None:
    # Recompute groups after a modification, then keep an accepted human
    # decision from being overwritten by the same pre-existing semantic flag.
    annotate_duplicate_groups(samples)
    for sample in samples:
        quality = sample.setdefault("quality", {})
        if quality.get("review_decision") in {"accept", "modify"} and sample.get("verification", {}).get("status") == "pass":
            if quality.get("failure_mode") not in {"license_unknown"}:
                quality["needs_human_review"] = False
                quality["failure_mode"] = None

    rejected = [sample for sample in samples if sample.get("quality", {}).get("review_disposition") == "rejected"]
    rejected_ids = {sample.get("id") for sample in rejected}
    active = [sample for sample in samples if sample.get("id") not in rejected_ids]
    gold = [sample for sample in active if curate_bucket(sample) == "gold"]
    silver = [sample for sample in active if curate_bucket(sample) == "silver"]
    human_review = [sample for sample in active if sample.get("quality", {}).get("needs_human_review")]
    _write_jsonl(output / "all.jsonl", samples)
    _write_jsonl(output / "gold.jsonl", gold)
    _write_jsonl(output / "silver.jsonl", silver)
    _write_jsonl(output / "human_review.jsonl", human_review)
    _write_jsonl(output / "rejected.jsonl", rejected)
    review_queue = build_review_queue(output)
    write_result_cards(output, samples, {"gold": gold, "silver": silver, "rejected": rejected})

    summary_path = output / "summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8")) if summary_path.exists() else {}
    summary.update({
        "total_candidates": len(samples),
        "gold": len(gold),
        "silver": len(silver),
        "rejected": len(rejected),
        "human_review": len(human_review),
        "review_queue": len(review_queue),
        "review_decisions": len(_read_jsonl(output / "review_decisions.jsonl")),
        "path_reproducibility": _rate(sum(s.get("verification", {}).get("status") == "pass" for s in samples), len(samples)),
        "failure_modes": _failure_modes(samples),
    })
    if "documents" in summary:
        counts: dict[str, dict[str, int]] = {}
        for sample in gold:
            counts.setdefault(sample.get("source", {}).get("doc_id", ""), {"gold": 0, "silver": 0})["gold"] += 1
        for sample in silver:
            counts.setdefault(sample.get("source", {}).get("doc_id", ""), {"gold": 0, "silver": 0})["silver"] += 1
        for document in summary["documents"]:
            document.update(counts.get(document.get("doc_id"), {"gold": 0, "silver": 0}))
    summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")


def _review_snapshot(sample: dict[str, Any]) -> dict[str, Any]:
    return {
        "verification_status": sample.get("verification", {}).get("status"),
        "failure_mode": sample.get("quality", {}).get("failure_mode"),
        "needs_human_review": sample.get("quality", {}).get("needs_human_review"),
        "answer": copy.deepcopy(sample.get("task", {}).get("answer", {})),
    }


def _decision_id(output: Path, sample_id: str, reviewer: str) -> str:
    existing = output / "review_decisions.jsonl"
    count = len(_read_jsonl(existing)) if existing.exists() else 0
    return f"review-{count + 1:06d}-{sample_id}-{reviewer}"


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _append_jsonl(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=True, sort_keys=True) + "\n")


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text("".join(json.dumps(row, ensure_ascii=True, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def _failure_modes(samples: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for sample in samples:
        mode = sample.get("quality", {}).get("failure_mode")
        if mode:
            counts[mode] = counts.get(mode, 0) + 1
    return counts


def _rate(numerator: int, denominator: int) -> float:
    return round(numerator / denominator, 4) if denominator else 0.0
