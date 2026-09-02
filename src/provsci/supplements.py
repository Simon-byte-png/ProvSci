"""Parse and attach externally fetched supplementary material.

The source fetcher deliberately stops at bytes plus a hash.  This module is
the next explicit step: parse the attachment with the existing adapter stack,
turn its paragraphs/tables/figures into a replayable supplement record, and
attach that record to a normalized article package.  The original article and
attachment remain immutable inputs; the output is a new package artifact.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from .adapters import load_document
from .models import DocumentPackage


class SupplementError(ValueError):
    """Raised when supplementary material cannot be parsed or attached."""


def parse_supplement_attachment(
    attachment_path: str | Path,
    supplement_id: str,
    *,
    href: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Parse one attachment and return a provenance-bearing supplement record."""
    path = Path(attachment_path)
    if not path.exists() or not path.is_file():
        raise SupplementError(f"supplement attachment not found: {path}")
    normalized_id = str(supplement_id).strip()
    if not normalized_id:
        raise SupplementError("supplement_id cannot be empty")
    try:
        document = load_document(path, metadata)
    except Exception as exc:
        raise SupplementError(f"could not parse supplement {path}: {exc}") from exc
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    text_parts = [str(paragraph.get("text", "")).strip() for paragraph in document.paragraphs]
    text_parts = [part for part in text_parts if part]
    # Keep table values in the textual channel as well.  This makes existing
    # supplement paths replayable while preserving structured table content
    # for future table-aware supplement mining.
    for table in document.tables:
        caption = str(table.get("caption", "")).strip()
        if caption:
            text_parts.append(caption)
        columns = [str(column) for column in table.get("columns", [])]
        for row in table.get("rows", []):
            values = []
            for column in columns or row.keys():
                value = str(row.get(column, "")).strip()
                if value:
                    values.append(f"{column}: {value}")
            if values:
                text_parts.append("; ".join(values))
    return {
        "id": normalized_id,
        "href": href,
        "local_path": str(path),
        "text": "\n".join(text_parts),
        "tables": list(document.tables),
        "figures": list(document.figures),
        "source_hash": digest,
        "source_version": f"sha256:{digest}",
        "parser": (document.metadata or {}).get("adapter", "unknown"),
        "metadata": dict(metadata or {}),
    }


def attach_supplement(
    article_path: str | Path,
    attachment_path: str | Path,
    output_path: str | Path,
    supplement_id: str,
    *,
    href: str | None = None,
    article_metadata: dict[str, Any] | None = None,
    supplement_metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Write a new normalized article package with one parsed supplement."""
    article = Path(article_path)
    attachment = Path(attachment_path)
    destination = Path(output_path)
    if article.resolve() == destination.resolve() or attachment.resolve() == destination.resolve():
        raise SupplementError("output_path must be different from both input files")
    try:
        document = load_document(article, article_metadata)
    except Exception as exc:
        raise SupplementError(f"could not parse article {article}: {exc}") from exc
    supplement = parse_supplement_attachment(
        attachment,
        supplement_id,
        href=href,
        metadata=supplement_metadata,
    )
    article_hash = hashlib.sha256(article.read_bytes()).hexdigest()
    merged_metadata = dict(document.metadata or {})
    merged_metadata.update({
        "adapter": "attached_package_v0.1",
        "base_document_path": str(article),
        "base_document_hash": article_hash,
        "supplement_count": len(document.supplements) + 1,
    })
    raw = {
        "doc_id": document.doc_id,
        "title": document.title,
        "year": document.year,
        "license": document.license,
        "local_path": str(destination),
        "paragraphs": list(document.paragraphs),
        "tables": list(document.tables),
        "figures": list(document.figures),
        "supplements": list(document.supplements) + [supplement],
        "metadata": merged_metadata,
    }
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(raw, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return {
        "output": str(destination),
        "doc_id": document.doc_id,
        "base_document_hash": article_hash,
        "supplement_id": supplement["id"],
        "supplement_hash": supplement["source_hash"],
        "supplement_parser": supplement["parser"],
        "supplement_tables": len(supplement.get("tables", [])),
        "supplement_figures": len(supplement.get("figures", [])),
        "supplement_text_chars": len(supplement.get("text", "")),
    }


def document_to_raw(document: DocumentPackage) -> dict[str, Any]:
    """Return a JSON-native representation for callers that already parsed an article."""
    return {
        "doc_id": document.doc_id,
        "title": document.title,
        "year": document.year,
        "license": document.license,
        "local_path": document.local_path,
        "paragraphs": list(document.paragraphs),
        "tables": list(document.tables),
        "figures": list(document.figures),
        "supplements": list(document.supplements),
        "metadata": dict(document.metadata),
    }
