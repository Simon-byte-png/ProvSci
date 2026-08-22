"""A small, runnable agent facade over the auditable pipeline.

This is intentionally deterministic in v0.3: model-backed candidate writing
can be plugged in later, but ingestion, verification, curation and evidence
lookup already form a usable agent API today.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .pipeline import run_pipeline


class ScientificDataAgent:
    def __init__(self, strategy: str = "result_focused") -> None:
        self.strategy = strategy
        self.last_run: Path | None = None

    def run(self, input_path: str | Path, output_dir: str | Path) -> dict[str, Any]:
        """Ingest, mine, verify and curate one scientific document."""
        self.last_run = Path(output_dir)
        return run_pipeline(input_path, output_dir, strategy=self.strategy)

    def ask(self, question: str, result_dir: str | Path | None = None, limit: int = 3) -> list[dict[str, Any]]:
        """Find verified results relevant to a natural-language question.

        This is a transparent lexical baseline, not an LLM claim. It returns
        the complete sample so a caller can inspect evidence and path trace.
        """
        directory = Path(result_dir) if result_dir is not None else self.last_run
        if directory is None:
            raise ValueError("run the agent first or provide result_dir")
        all_path = directory / "all.jsonl"
        if not all_path.exists():
            raise FileNotFoundError(f"pipeline results not found: {all_path}")
        query_tokens = _tokens(question)
        ranked = []
        for line in all_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            sample = json.loads(line)
            if sample.get("verification", {}).get("status") != "pass":
                continue
            searchable = " ".join([
                str(sample.get("task", {}).get("question", "")),
                str(sample.get("task", {}).get("subject", "")),
                str(sample.get("task", {}).get("answer", {}).get("display", "")),
                str(sample.get("task", {}).get("answer", {}).get("metric", "")),
                str(sample.get("task", {}).get("answer", {}).get("entity", "")),
            ])
            score = len(query_tokens & _tokens(searchable))
            if score:
                ranked.append((score, sample))
        ranked.sort(key=lambda item: (-item[0], item[1].get("id", "")))
        return [sample for _, sample in ranked[: max(1, limit)]]


def _tokens(value: str) -> set[str]:
    return {token for token in re.findall(r"[a-z0-9μµ%]+", value.casefold()) if len(token) > 1}
