"""Command line interface for the ProvSci v0 pipeline."""

from __future__ import annotations

import argparse
import json
import sys

from .pipeline import run_pipeline
from .batch import read_manifest_entries, run_batch
from .evaluate import evaluate_manifest
from .agent import ScientificDataAgent


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="provsci", description="Run the auditable scientific data pipeline")
    subparsers = parser.add_subparsers(dest="command", required=True)
    run = subparsers.add_parser("run", help="mine, verify and curate one document package")
    run.add_argument("--input", required=True, help="normalized document package JSON")
    run.add_argument("--output", required=True, help="directory for JSONL and summary artifacts")
    run.add_argument("--strategy", choices=["table_only", "full", "result_focused", "multimodal"], default="result_focused")
    batch = subparsers.add_parser("batch", help="run multiple document packages/files")
    batch.add_argument("--manifest", required=True, help="JSON manifest with a documents list")
    batch.add_argument("--output", required=True, help="directory for batch artifacts")
    batch.add_argument("--strategy", choices=["table_only", "full", "result_focused", "multimodal"], default="result_focused")
    evaluate = subparsers.add_parser("evaluate", help="run the reproducible manifest benchmark")
    evaluate.add_argument("--manifest", required=True, help="JSON benchmark manifest")
    evaluate.add_argument("--output", required=True, help="directory for benchmark artifacts")
    ask = subparsers.add_parser("ask", help="query verified results from a completed run")
    ask.add_argument("--results", required=True, help="directory containing all.jsonl")
    ask.add_argument("--question", required=True, help="natural-language result question")
    ask.add_argument("--limit", type=int, default=3)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "run":
        summary = run_pipeline(args.input, args.output, strategy=args.strategy)
        print(json.dumps(summary, indent=2, ensure_ascii=False))
        return 0
    if args.command == "batch":
        summary = run_batch(read_manifest_entries(args.manifest), args.output, strategy=args.strategy)
        print(json.dumps(summary, indent=2, ensure_ascii=False))
        return 0
    if args.command == "evaluate":
        summary = evaluate_manifest(args.manifest, args.output)
        print(json.dumps(summary, indent=2, ensure_ascii=False))
        return 0
    if args.command == "ask":
        results = ScientificDataAgent().ask(args.question, args.results, args.limit)
        print(json.dumps(results, indent=2, ensure_ascii=False))
        return 0
    return 2


if __name__ == "__main__":
    sys.exit(main())
