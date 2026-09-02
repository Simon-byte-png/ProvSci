#!/usr/bin/env python3
"""Build reproducible review figures from a literature matrix.

The script intentionally uses only the Python standard library.  It writes
SVG files with source IDs linked to the matrix URLs, plus normalized CSV/JSON
artifacts so a reviewer can inspect or replot the same data.  The figures are
qualitative review aids, not a performance leaderboard.
"""

from __future__ import annotations

import argparse
import csv
import html
import json
from collections import Counter
from pathlib import Path
from typing import Any, Iterable


REQUIRED_FIELDS = {
    "id", "year", "title", "type", "source_url", "domain", "inputs", "parser",
    "extraction_objects", "model_family", "uses_llm_vlm", "agentic",
    "evidence_granularity", "verification", "human_in_loop", "data_scale",
    "reported_metrics", "openness", "limitation_tags", "limitations", "provsci_role",
}

CAPABILITIES = ["text", "table", "figure", "formula", "evidence", "verification", "agentic"]
STAGES = ["discovery", "parsing", "extraction", "normalization", "path", "verification", "review", "export"]
COLORS = {
    "background": "#f8fafc",
    "ink": "#172033",
    "muted": "#526071",
    "grid": "#d8e0ea",
    "accent": "#2563eb",
    "accent2": "#0f766e",
    "positive": "#0f766e",
    "negative": "#e2e8f0",
    "warning": "#d97706",
    "danger": "#b91c1c",
}


def load_matrix(path: str | Path) -> dict[str, Any]:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    records = raw.get("records")
    if not isinstance(records, list) or not records:
        raise ValueError("literature matrix must contain a non-empty records list")
    seen: set[str] = set()
    for index, record in enumerate(records):
        missing = REQUIRED_FIELDS - set(record)
        if missing:
            raise ValueError(f"record {index} ({record.get('id')!r}) missing: {sorted(missing)}")
        identifier = str(record["id"])
        if identifier in seen:
            raise ValueError(f"duplicate literature record id: {identifier}")
        seen.add(identifier)
        if not isinstance(record["year"], int):
            raise ValueError(f"record {identifier} year must be an integer")
        if not isinstance(record["inputs"], list) or not record["inputs"]:
            raise ValueError(f"record {identifier} inputs must be non-empty")
        if not isinstance(record["source_url"], str) or not record["source_url"].startswith(("http://", "https://")):
            raise ValueError(f"record {identifier} source_url must be an HTTP(S) URL")
    return raw


def normalized_records(matrix: dict[str, Any]) -> list[dict[str, Any]]:
    """Return stable, shallow records for CSV and derived summaries."""
    records = []
    for record in sorted(matrix["records"], key=lambda item: (item["year"], item["id"])):
        row = dict(record)
        for key in ("domain", "inputs", "parser", "extraction_objects", "evidence_granularity", "verification", "reported_metrics", "limitation_tags", "limitations"):
            row[key] = list(row.get(key) or [])
        records.append(row)
    return records


def summarize(records: Iterable[dict[str, Any]]) -> dict[str, Any]:
    rows = list(records)
    return {
        "record_count": len(rows),
        "year_range": [min(row["year"] for row in rows), max(row["year"] for row in rows)],
        "counts": {
            "by_year": dict(sorted(Counter(str(row["year"]) for row in rows).items())),
            "by_type": dict(sorted(Counter(row["type"] for row in rows).items())),
            "by_model_family": dict(sorted(Counter(row["model_family"] for row in rows).items())),
            "by_domain": dict(sorted(Counter(domain for row in rows for domain in row["domain"]).items())),
            "by_input": dict(sorted(Counter(value for row in rows for value in row["inputs"]).items())),
            "by_evidence_granularity": dict(sorted(Counter(value for row in rows for value in row["evidence_granularity"]).items())),
            "by_verification": dict(sorted(Counter(value for row in rows for value in row["verification"]).items())),
            "by_limitation_tag": dict(sorted(Counter(value for row in rows for value in row["limitation_tags"]).items())),
        },
        "qualitative_policy": "Counts describe encoded capabilities and limitations; they are not accuracy, cost, or quality scores.",
    }


def write_csv(path: Path, records: list[dict[str, Any]]) -> None:
    fields = [
        "id", "year", "year_basis", "title", "type", "source_url", "paper_url", "domain",
        "inputs", "parser", "extraction_objects", "model_family", "uses_llm_vlm", "agentic",
        "evidence_granularity", "verification", "human_in_loop", "data_scale", "reported_metrics",
        "code_url", "data_url", "openness", "limitation_tags", "limitations", "provsci_role",
    ]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for record in records:
            row = dict(record)
            for key in fields:
                if isinstance(row.get(key), list):
                    row[key] = "; ".join(str(item) for item in row[key])
                elif row.get(key) is None:
                    row[key] = ""
            writer.writerow({key: row.get(key, "") for key in fields})


def svg_header(width: int, height: int, title: str, description: str) -> str:
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" '
        f'width="{width}" height="{height}" viewBox="0 0 {width} {height}">\n'
        f'<title>{html.escape(title)}</title><desc>{html.escape(description)}</desc>\n'
        f'<rect width="100%" height="100%" fill="{COLORS["background"]}"/>\n'
        f'<style>text{{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;fill:{COLORS["ink"]}}}'
        f'.muted{{fill:{COLORS["muted"]}}}.small{{font-size:11px}}.label{{font-size:12px}}'
        f'.title{{font-size:20px;font-weight:700}}.axis{{stroke:{COLORS["grid"]};stroke-width:1}}'
        f'</style>\n'
    )


def svg_footer() -> str:
    return "</svg>\n"


def safe_text(value: Any) -> str:
    return html.escape(str(value))


def record_link(record: dict[str, Any]) -> str:
    return safe_text(record.get("source_url", ""))


def build_timeline(records: list[dict[str, Any]]) -> str:
    width, height = 1500, 760
    left, right, top, bottom = 180, 40, 90, 80
    min_year, max_year = min(row["year"] for row in records), max(row["year"] for row in records)
    span = max(1, max_year - min_year)
    families = sorted({row["model_family"] for row in records})
    row_height = max(42, min(68, (height - top - bottom) // max(1, len(families))))
    parts = [svg_header(width, height, "Technology timeline", "Each point links to the corresponding source URL in the literature matrix."),
             '<text x="40" y="42" class="title">Technology timeline (qualitative milestones)</text>',
             '<text x="40" y="66" class="muted small">Year is a publication/release period encoded in the matrix; overlapping points are intentionally not ranked.</text>']
    x0, x1 = left, width - right
    for tick in range((min_year // 5) * 5, max_year + 1, 5):
        x = x0 + (tick - min_year) / span * (x1 - x0)
        parts.append(f'<line x1="{x:.1f}" y1="{top-10}" x2="{x:.1f}" y2="{height-bottom}" class="axis"/>')
        parts.append(f'<text x="{x:.1f}" y="{height-bottom+25}" text-anchor="middle" class="muted small">{tick}</text>')
    for index, family in enumerate(families):
        y = top + index * row_height + row_height / 2
        parts.append(f'<line x1="{x0}" y1="{y:.1f}" x2="{x1}" y2="{y:.1f}" stroke="{COLORS["grid"]}" stroke-dasharray="3 4"/>')
        parts.append(f'<text x="{x0-12}" y="{y+4:.1f}" text-anchor="end" class="label">{safe_text(family)}</text>')
        family_records = [row for row in records if row["model_family"] == family]
        for item_index, record in enumerate(family_records):
            x = x0 + (record["year"] - min_year) / span * (x1 - x0)
            y_offset = ((item_index % 3) - 1) * 11
            cy = y + y_offset
            radius = 7 if record["agentic"] else 5
            color = COLORS["accent2"] if record["uses_llm_vlm"] else COLORS["accent"]
            label_y = cy - 12 if item_index % 2 == 0 else cy + 22
            parts.append(f'<a xlink:href="{record_link(record)}" target="_blank"><circle cx="{x:.1f}" cy="{cy:.1f}" r="{radius}" fill="{color}" stroke="white" stroke-width="2"><title>{safe_text(record["id"])} — {safe_text(record["title"])}</title></circle>')
            parts.append(f'<text x="{x:.1f}" y="{label_y:.1f}" text-anchor="middle" class="small">{safe_text(record["id"])}</text></a>')
    parts.append('<text x="40" y="730" class="muted small">Blue = non-LLM/specialized or corpus pipeline; teal = LLM/VLM involved. Circle size highlights agentic orchestration, not performance.</text>')
    parts.append(svg_footer())
    return "\n".join(parts)


def capability_flags(record: dict[str, Any]) -> dict[str, bool]:
    inputs = set(record["inputs"])
    objects = set(record["extraction_objects"])
    evidence = set(record["evidence_granularity"])
    verification = set(record["verification"])
    return {
        "text": bool(inputs & {"text", "html", "pdf", "jats", "xml"}),
        "table": bool(inputs & {"table", "tables", "table_image"}) or bool({"table", "tables", "table_values", "table_cell", "cell_bbox", "row_and_column_structure", "table_bbox"} & evidence) or bool(objects & {"tables", "table", "table_values", "rows", "columns", "cells", "headers", "table_image"}),
        "figure": bool(inputs & {"figure", "figures", "images"}) or bool({"figure_caption", "figure", "figure_bbox"} & evidence),
        "formula": bool(inputs & {"formula"}) or bool(objects & {"formula", "formulas"}),
        "evidence": bool(evidence),
        "verification": bool(verification) and not (verification == {"format_checks"}),
        "agentic": bool(record["agentic"]),
    }


def build_capability_matrix(records: list[dict[str, Any]]) -> str:
    cell = 70
    left, top = 270, 100
    width, height = left + cell * len(CAPABILITIES) + 40, top + 34 * len(records) + 80
    parts = [svg_header(width, height, "System capability matrix", "Boolean capabilities derived from encoded inputs, evidence and verification fields."),
             '<text x="40" y="42" class="title">System capability matrix</text>',
             '<text x="40" y="66" class="muted small">A filled cell means the matrix records that capability; absence means unknown or not core, not proof of inability.</text>']
    for col, capability in enumerate(CAPABILITIES):
        x = left + col * cell + cell / 2
        parts.append(f'<text x="{x:.1f}" y="88" text-anchor="middle" class="label">{safe_text(capability)}</text>')
    for row_index, record in enumerate(records):
        y = top + row_index * 34
        parts.append(f'<a xlink:href="{record_link(record)}" target="_blank"><text x="{left-12}" y="{y+21}" text-anchor="end" class="small">{safe_text(record["id"])}</text></a>')
        flags = capability_flags(record)
        for col, capability in enumerate(CAPABILITIES):
            x = left + col * cell + 8
            color = COLORS["positive"] if flags[capability] else COLORS["negative"]
            parts.append(f'<rect x="{x}" y="{y+5}" width="{cell-16}" height="24" rx="4" fill="{color}"><title>{safe_text(record["id"])}: {capability}={str(flags[capability]).lower()}</title></rect>')
    legend_y = top + 34 * len(records) + 35
    parts.append(f'<rect x="{left}" y="{legend_y-13}" width="18" height="18" rx="3" fill="{COLORS["positive"]}"/><text x="{left+26}" y="{legend_y}" class="small">encoded capability</text>')
    parts.append(f'<rect x="{left+180}" y="{legend_y-13}" width="18" height="18" rx="3" fill="{COLORS["negative"]}"/><text x="{left+206}" y="{legend_y}" class="small">not encoded / unknown</text>')
    parts.append(svg_footer())
    return "\n".join(parts)


def build_evidence_chain(records: list[dict[str, Any]]) -> str:
    width, height = 1500, 480
    margin = 50
    box_w, box_h, gap = 150, 84, 28
    y = 165
    counts = {
        "discovery": len(records),
        "parsing": sum(bool(row["parser"]) for row in records),
        "extraction": sum(bool(row["extraction_objects"]) for row in records),
        "normalization": sum(any(value in row["extraction_objects"] for value in ("properties", "attributes", "entity_links", "structured_records")) for row in records),
        "path": sum("query_replay" in row["verification"] or "tool_trace_if_available" in row["verification"] for row in records),
        "verification": sum(bool(row["verification"]) for row in records),
        "review": sum(row["human_in_loop"] not in {"not_core", "optional_configuration_and_review"} for row in records),
        "export": sum(row["type"] in {"structured_corpus", "knowledge_graph_visualization", "table_dataset", "scientific_qa_dataset"} for row in records),
    }
    parts = [svg_header(width, height, "Evidence chain", "The flow is a design abstraction; numbers are counts of matrix records mentioning each stage, not throughput."),
             '<text x="40" y="42" class="title">From source document to auditable data</text>',
             '<text x="40" y="66" class="muted small">Counts below are encoded coverage signals, not measured system throughput or accuracy.</text>']
    x = margin
    for index, stage in enumerate(STAGES):
        if index:
            prev_x = x - gap - box_w
            parts.append(f'<line x1="{prev_x+box_w}" y1="{y+box_h/2}" x2="{x}" y2="{y+box_h/2}" stroke="{COLORS["accent"]}" stroke-width="2" marker-end="url(#arrow)"/>')
        fill = COLORS["accent2"] if stage in {"verification", "review"} else COLORS["accent"]
        parts.append(f'<rect x="{x}" y="{y}" width="{box_w}" height="{box_h}" rx="12" fill="{fill}"/>')
        parts.append(f'<text x="{x+box_w/2}" y="{y+34}" text-anchor="middle" fill="white" style="font-size:15px;font-weight:700">{safe_text(stage)}</text>')
        parts.append(f'<text x="{x+box_w/2}" y="{y+59}" text-anchor="middle" fill="white" class="small">{counts[stage]} records</text>')
        x += box_w + gap
    # Insert the marker definition after the root style; SVG accepts it near the end.
    parts.insert(1, '<defs><marker id="arrow" markerWidth="8" markerHeight="8" refX="7" refY="3" orient="auto"><path d="M0,0 L0,6 L7,3 z" fill="#2563eb"/></marker></defs>')
    parts.append('<text x="50" y="330" class="label">ProvSci design boundary</text>')
    parts.append('<text x="50" y="355" class="muted small">A source citation or model trace becomes a Gold result only after evidence resolution, deterministic path replay, license checks and quality gating.</text>')
    parts.append('<text x="50" y="395" class="muted small">Matrix fields preserve links to the original source URL; ResultCard outputs additionally preserve locator, raw/normalized value and verifier trace.</text>')
    parts.append(svg_footer())
    return "\n".join(parts)


def build_failure_modes(records: list[dict[str, Any]]) -> str:
    counts = Counter(tag for row in records for tag in row["limitation_tags"])
    ranked = sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    width, height = 1100, max(460, 150 + 38 * len(ranked))
    left, right, top = 300, 80, 100
    max_count = max(counts.values()) if counts else 1
    chart_w = width - left - right
    parts = [svg_header(width, height, "Failure and limitation modes", "Counts are derived from qualitative limitation tags in the literature matrix."),
             '<text x="40" y="42" class="title">Where existing systems leave risk</text>',
             '<text x="40" y="66" class="muted small">A tag is a coded limitation mention, not a measured failure rate; source IDs remain available in the matrix.</text>']
    for index, (tag, count) in enumerate(ranked):
        y = top + index * 38
        bar_w = count / max_count * chart_w
        parts.append(f'<text x="{left-14}" y="{y+21}" text-anchor="end" class="label">{safe_text(tag)}</text>')
        parts.append(f'<rect x="{left}" y="{y+5}" width="{bar_w:.1f}" height="24" rx="4" fill="{COLORS["warning"]}"><title>{safe_text(tag)}: {count} encoded mentions</title></rect>')
        parts.append(f'<text x="{left+bar_w+8:.1f}" y="{y+22}" class="label">{count}</text>')
    source_y = top + len(ranked) * 38 + 35
    parts.append(f'<text x="40" y="{source_y}" class="muted small">Tags are counted across {len(records)} records. Typical ProvSci controls: evidence locator, unit/condition binding, path replay, license gate and human review.</text>')
    parts.append(svg_footer())
    return "\n".join(parts)


def build_review_artifacts(input_path: str | Path, output_dir: str | Path) -> dict[str, Any]:
    matrix = load_matrix(input_path)
    records = normalized_records(matrix)
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    (output / "literature_matrix.normalized.json").write_text(
        json.dumps({**matrix, "records": records}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    write_csv(output / "literature_matrix.csv", records)
    summary = summarize(records)
    (output / "literature_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    figures = {
        "timeline": build_timeline(records),
        "capability_matrix": build_capability_matrix(records),
        "evidence_chain": build_evidence_chain(records),
        "failure_modes": build_failure_modes(records),
    }
    for name, content in figures.items():
        (output / f"{name}.svg").write_text(content, encoding="utf-8")
    manifest = {
        "schema_version": "provsci.review_figures.v1",
        "input": str(Path(input_path)),
        "record_count": len(records),
        "artifacts": [
            "literature_matrix.normalized.json", "literature_matrix.csv", "literature_summary.json",
            "timeline.svg", "capability_matrix.svg", "evidence_chain.svg", "failure_modes.svg",
        ],
        "figures_are_qualitative": True,
        "source_links": True,
    }
    (output / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build reproducible ProvSci review figures")
    parser.add_argument("--input", default="examples/review/literature_matrix.json", help="literature matrix JSON")
    parser.add_argument("--output", default="work/review-figures", help="output directory")
    args = parser.parse_args(argv)
    result = build_review_artifacts(args.input, args.output)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
