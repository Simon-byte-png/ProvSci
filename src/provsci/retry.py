"""Reproducible retry orchestration for a completed pipeline run."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from .batch import run_batch
from .pipeline import run_pipeline


STRATEGIES = {"table_only", "full", "result_focused", "multimodal"}


class RetryError(ValueError):
    """Raised when a previous run cannot be replayed safely."""


def fallback_strategy(previous: str) -> str:
    """Choose a higher-recall strategy for a manual retry."""
    return {
        "table_only": "result_focused",
        "result_focused": "multimodal",
        "full": "multimodal",
        "multimodal": "full",
    }.get(str(previous), "result_focused")


def retry_run(
    run_dir: str | Path,
    output_dir: str | Path,
    strategy: str | None = None,
) -> dict[str, Any]:
    """Re-run the inputs of a previous single or batch run.

    The original artifacts are never overwritten.  The new summary and
    ``retry.json`` identify the source run, its summary hash, the selected
    strategy and all resolved input paths.  A caller may select a strategy;
    otherwise a deterministic higher-recall fallback is used.
    """
    source_dir = Path(run_dir)
    summary_path = source_dir / "summary.json"
    if not summary_path.exists():
        raise RetryError(f"previous run summary not found: {summary_path}")
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    previous_strategy = str(summary.get("strategy", "result_focused"))
    selected_strategy = str(strategy or fallback_strategy(previous_strategy))
    if selected_strategy not in STRATEGIES:
        raise RetryError(f"strategy must be one of {sorted(STRATEGIES)}")
    output = Path(output_dir)
    if output.resolve() == source_dir.resolve():
        raise RetryError("retry output must be different from the previous run directory")

    documents = summary.get("documents")
    if isinstance(documents, list) and documents:
        entries: list[tuple[Path, dict[str, Any]]] = []
        for row in documents:
            input_path = _resolve_input(source_dir, row.get("input"))
            if input_path is None:
                raise RetryError(f"retry input not found for {row.get('doc_id')}: {row.get('input')}")
            entries.append((input_path, _metadata_from_source(row.get("source", {}))))
        result = run_batch(entries, output, strategy=selected_strategy)
    else:
        input_path = _resolve_input(source_dir, summary.get("input"))
        if input_path is None:
            raise RetryError(f"retry input not found: {summary.get('input')}")
        result = run_pipeline(input_path, output, strategy=selected_strategy)

    retry_info = {
        "retry_of": str(source_dir.resolve()),
        "previous_summary_hash": hashlib.sha256(summary_path.read_bytes()).hexdigest(),
        "previous_strategy": previous_strategy,
        "strategy": selected_strategy,
        "resolved_inputs": [str(path) for path in _resolved_inputs(summary, source_dir)],
    }
    (output / "retry.json").write_text(json.dumps(retry_info, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    result.update({
        "retry_of": retry_info["retry_of"],
        "retry_strategy": selected_strategy,
        "previous_summary_hash": retry_info["previous_summary_hash"],
    })
    (output / "summary.json").write_text(json.dumps(result, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    return result


def _metadata_from_source(source: Any) -> dict[str, Any]:
    if not isinstance(source, dict):
        return {}
    keys = {
        "doc_id", "title", "year", "license", "local_path", "domain", "source_url",
        "retrieved_at", "license_source", "adapter", "source_version", "retrieval_method", "doi", "pmid",
    }
    return {key: source[key] for key in keys if key in source}


def _resolve_input(run_dir: Path, raw: Any) -> Path | None:
    if not raw:
        return None
    path = Path(str(raw))
    candidates = [path] if path.is_absolute() else [path, run_dir / path, run_dir.parent / path, Path.cwd() / path]
    return next((candidate for candidate in candidates if candidate.exists()), None)


def _resolved_inputs(summary: dict[str, Any], run_dir: Path) -> list[Path]:
    rows = summary.get("documents")
    raw_paths = [row.get("input") for row in rows if isinstance(row, dict)] if isinstance(rows, list) else [summary.get("input")]
    return [path for raw in raw_paths if (path := _resolve_input(run_dir, raw)) is not None]
