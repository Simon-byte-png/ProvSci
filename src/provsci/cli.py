"""Command line interface for the ProvSci v0 pipeline."""

from __future__ import annotations

import argparse
import json
import sys

from .pipeline import run_pipeline
from .batch import read_manifest_entries, run_batch
from .evaluate import evaluate_manifest
from .agent import ScientificDataAgent
from .review import ReviewError, build_review_queue, record_review_decision
from .retry import retry_run
from .ablation import evaluate_module_ablation
from .adversarial import evaluate_adversarial_cases
from .sources import fetch_europepmc_jats, fetch_external_supplement, fetch_http_source, search_europepmc
from .supplements import attach_supplement
from .review_ui import build_review_html, serve_review_workbench


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="provsci", description="Run the auditable scientific data pipeline")
    subparsers = parser.add_subparsers(dest="command", required=True)
    run = subparsers.add_parser("run", help="mine, verify and curate one document package")
    run.add_argument("--input", required=True, help="normalized document package JSON")
    run.add_argument("--output", required=True, help="directory for JSONL and summary artifacts")
    run.add_argument("--strategy", choices=["table_only", "full", "result_focused", "multimodal"], default="result_focused")
    run.add_argument("--domain", default=None, help="optional ResultCard profile/domain; defaults to scientific_quantitative_result_v1")
    batch = subparsers.add_parser("batch", help="run multiple document packages/files")
    batch.add_argument("--manifest", required=True, help="JSON manifest with a documents list")
    batch.add_argument("--output", required=True, help="directory for batch artifacts")
    batch.add_argument("--strategy", choices=["table_only", "full", "result_focused", "multimodal"], default="result_focused")
    evaluate = subparsers.add_parser("evaluate", help="run the reproducible manifest benchmark")
    evaluate.add_argument("--manifest", required=True, help="JSON benchmark manifest")
    evaluate.add_argument("--output", required=True, help="directory for benchmark artifacts")
    ablate = subparsers.add_parser("ablate", help="run diagnostic module ablations on a fixed manifest")
    ablate.add_argument("--manifest", required=True, help="JSON benchmark manifest")
    ablate.add_argument("--output", required=True, help="directory for ablation artifacts")
    ablate.add_argument("--strategy", choices=["table_only", "full", "result_focused", "multimodal"], default="result_focused")
    adversarial = subparsers.add_parser("adversarial", help="run deterministic verifier contamination cases")
    adversarial.add_argument("--manifest", required=True, help="JSON benchmark manifest")
    adversarial.add_argument("--output", required=True, help="directory for adversarial artifacts")
    adversarial.add_argument("--strategy", choices=["table_only", "full", "result_focused", "multimodal"], default="result_focused")
    ask = subparsers.add_parser("ask", help="query verified results from a completed run")
    ask.add_argument("--results", required=True, help="directory containing all.jsonl")
    ask.add_argument("--question", required=True, help="natural-language result question")
    ask.add_argument("--limit", type=int, default=3)
    fetch = subparsers.add_parser("fetch-pmc", help="fetch a licensed Europe PMC JATS article")
    fetch.add_argument("--pmc-id", required=True, help="PMC identifier, e.g. PMC13272437")
    fetch.add_argument("--output", required=True, help="destination .nxml path")
    fetch_url = subparsers.add_parser("fetch-url", help="fetch one HTTP(S) source with hash/license provenance")
    fetch_url.add_argument("--url", required=True, help="HTTP(S) source URL, DOI resolver URL or repository URL")
    fetch_url.add_argument("--output", required=True, help="destination source file")
    fetch_url.add_argument("--max-bytes", type=int, default=100 * 1024 * 1024, help="maximum response size")
    search = subparsers.add_parser("search-pmc", help="discover Europe PMC open-access candidates")
    search.add_argument("--query", required=True, help="Europe PMC query")
    search.add_argument("--limit", type=int, default=10)
    supplement = subparsers.add_parser("fetch-supplement", help="fetch one external supplementary attachment")
    supplement.add_argument("--article-url", required=True, help="article or full-text URL used to resolve href")
    supplement.add_argument("--href", required=True, help="relative or absolute supplementary link")
    supplement.add_argument("--output", required=True, help="destination attachment path")
    attach = subparsers.add_parser("attach-supplement", help="parse an attachment and attach it to a new article package")
    attach.add_argument("--article", required=True, help="article JSON/JATS/document-package path")
    attach.add_argument("--supplement", required=True, help="downloaded supplementary attachment path")
    attach.add_argument("--supplement-id", required=True, help="stable supplement identifier")
    attach.add_argument("--href", default=None, help="original attachment href, if available")
    attach.add_argument("--output", required=True, help="new normalized article-package JSON path")
    review = subparsers.add_parser("review", help="record and materialize a human-review decision")
    review.add_argument("--run", required=True, help="completed pipeline run directory")
    review.add_argument("--sample-id", required=True, help="sample ID from human_review.jsonl")
    review.add_argument("--decision", choices=["accept", "modify", "reject"], required=True)
    review.add_argument("--reviewer", required=True, help="reviewer identity")
    review.add_argument("--comment", default="", help="optional review rationale")
    review.add_argument(
        "--changes-json",
        default=None,
        help="JSON object of dotted field paths to values; required for modify",
    )
    review_queue = subparsers.add_parser("review-queue", help="rank active human-review samples")
    review_queue.add_argument("--run", required=True, help="completed pipeline run directory")
    review_queue.add_argument("--output", default=None, help="optional JSONL destination; defaults to <run>/review_queue.jsonl")
    review_ui = subparsers.add_parser("review-ui", help="write a local HTML review-workbench snapshot")
    review_ui.add_argument("--run", required=True, help="completed pipeline run directory")
    review_ui.add_argument("--output", default=None, help="HTML destination; defaults to <run>/review_workbench.html")
    review_serve = subparsers.add_parser("review-serve", help="serve the local interactive review workbench")
    review_serve.add_argument("--run", required=True, help="completed pipeline run directory")
    review_serve.add_argument("--host", default="127.0.0.1", help="loopback bind address (127.0.0.1 or localhost only)")
    review_serve.add_argument("--port", type=int, default=8765, help="HTTP port")
    retry = subparsers.add_parser("retry", help="re-run a completed run with a fallback or selected strategy")
    retry.add_argument("--run", required=True, help="previous pipeline run directory")
    retry.add_argument("--output", required=True, help="new output directory; must differ from --run")
    retry.add_argument("--strategy", choices=["table_only", "full", "result_focused", "multimodal"], default=None)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "run":
        metadata = {"domain": args.domain} if args.domain else None
        summary = run_pipeline(args.input, args.output, strategy=args.strategy, metadata=metadata)
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
    if args.command == "ablate":
        summary = evaluate_module_ablation(args.manifest, args.output, strategy=args.strategy)
        print(json.dumps(summary, indent=2, ensure_ascii=False))
        return 0
    if args.command == "adversarial":
        summary = evaluate_adversarial_cases(args.manifest, args.output, strategy=args.strategy)
        print(json.dumps(summary, indent=2, ensure_ascii=False))
        return 0
    if args.command == "ask":
        results = ScientificDataAgent().ask(args.question, args.results, args.limit)
        print(json.dumps(results, indent=2, ensure_ascii=False))
        return 0
    if args.command == "fetch-pmc":
        print(json.dumps(fetch_europepmc_jats(args.pmc_id, args.output), indent=2, ensure_ascii=False))
        return 0
    if args.command == "fetch-url":
        print(json.dumps(fetch_http_source(args.url, args.output, max_bytes=args.max_bytes), indent=2, ensure_ascii=False))
        return 0
    if args.command == "search-pmc":
        print(json.dumps(search_europepmc(args.query, args.limit), indent=2, ensure_ascii=False))
        return 0
    if args.command == "fetch-supplement":
        print(json.dumps(fetch_external_supplement(args.article_url, args.href, args.output), indent=2, ensure_ascii=False))
        return 0
    if args.command == "attach-supplement":
        print(json.dumps(attach_supplement(
            args.article,
            args.supplement,
            args.output,
            args.supplement_id,
            href=args.href,
        ), indent=2, ensure_ascii=False))
        return 0
    if args.command == "review":
        changes = None
        if args.changes_json is not None:
            try:
                changes = json.loads(args.changes_json)
            except json.JSONDecodeError as exc:
                raise ReviewError(f"--changes-json must be valid JSON: {exc}") from exc
        record = record_review_decision(
            args.run,
            args.sample_id,
            args.decision,
            args.reviewer,
            comment=args.comment,
            changes=changes,
        )
        print(json.dumps(record, indent=2, ensure_ascii=False))
        return 0
    if args.command == "review-queue":
        queue = build_review_queue(args.run, args.output)
        print(json.dumps({"count": len(queue), "items": queue}, indent=2, ensure_ascii=False))
        return 0
    if args.command == "review-ui":
        path = build_review_html(args.run, args.output)
        print(json.dumps({"output": str(path), "interactive_server": "provsci review-serve --run " + str(args.run)}, ensure_ascii=False))
        return 0
    if args.command == "review-serve":
        serve_review_workbench(args.run, args.host, args.port)
        return 0
    if args.command == "retry":
        summary = retry_run(args.run, args.output, strategy=args.strategy)
        print(json.dumps(summary, indent=2, ensure_ascii=False))
        return 0
    return 2


if __name__ == "__main__":
    sys.exit(main())
