"""Optional layout-aware document adapters.

The core package intentionally has no Docling dependency.  ``DoclingAdapter``
loads that dependency lazily (or accepts an injected converter factory for
tests/embedding), converts the exported Docling document into ProvSci's stable
``DocumentPackage`` shape, and records parser metadata.  Missing optional
dependencies fail explicitly at the adapter boundary instead of silently
falling back to an inaccurate parser.
"""

from __future__ import annotations

import importlib
import re
from pathlib import Path
from typing import Any, Callable

from .adapters import AdapterError, DocumentAdapter
from .models import DocumentPackage


class OptionalParserUnavailable(AdapterError):
    """Raised when a requested optional layout parser is not installed."""


class DoclingAdapter:
    """Convert Docling output into a ProvSci ``DocumentPackage``.

    ``converter_factory`` is intentionally injectable.  Production callers
    normally omit it and the adapter imports ``docling`` lazily; tests and
    downstream integrations can provide a compatible factory without adding a
    dependency to ProvSci's core runtime.
    """

    name = "docling_v0.1"

    def __init__(self, converter_factory: Callable[[], Any] | None = None) -> None:
        self._converter_factory = converter_factory

    def supports(self, source: Path) -> bool:
        return source.suffix.casefold() in {".pdf", ".docx", ".html", ".htm", ".md", ".markdown", ".pptx"}

    def load(self, source: Path, metadata: dict[str, Any] | None = None) -> DocumentPackage:
        if not self.supports(source):
            raise AdapterError(f"DoclingAdapter does not support {source.suffix or '<no suffix>'}")
        converter = self._converter()
        try:
            converted = converter.convert(str(source))
            document = getattr(converted, "document", converted)
            exported = self._export(document)
        except OptionalParserUnavailable:
            raise
        except Exception as exc:  # pragma: no cover - third-party boundary
            raise AdapterError(f"Docling failed to parse {source}: {exc}") from exc
        return self._to_package(source, exported, metadata)

    def _converter(self) -> Any:
        if self._converter_factory is not None:
            return self._converter_factory()
        try:
            module = importlib.import_module("docling.document_converter")
            factory = getattr(module, "DocumentConverter")
        except (ImportError, AttributeError) as exc:
            raise OptionalParserUnavailable(
                "DoclingAdapter requires optional dependency 'docling'; "
                "install it separately or inject converter_factory"
            ) from exc
        return factory()

    @staticmethod
    def _export(document: Any) -> dict[str, Any] | str:
        if isinstance(document, dict):
            return document
        exporter = getattr(document, "export_to_dict", None)
        if callable(exporter):
            exported = exporter()
            if isinstance(exported, dict):
                return exported
        markdown_exporter = getattr(document, "export_to_markdown", None)
        if callable(markdown_exporter):
            markdown = markdown_exporter()
            if isinstance(markdown, str) and markdown.strip():
                return markdown
        raise AdapterError("Docling document exposes neither export_to_dict nor export_to_markdown")

    def _to_package(
        self,
        source: Path,
        exported: dict[str, Any] | str,
        metadata: dict[str, Any] | None,
    ) -> DocumentPackage:
        supplied = dict(metadata or {})
        if isinstance(exported, str):
            paragraphs = _markdown_paragraphs(exported)
            tables: list[dict[str, Any]] = []
            figures: list[dict[str, Any]] = []
            export_mode = "markdown_fallback"
            parser_version = "unknown"
            title = supplied.get("title") or source.stem
        else:
            paragraphs = _docling_texts(exported)
            tables = _docling_tables(exported)
            figures = _docling_figures(exported)
            export_mode = "structured_dict"
            parser_version = str(exported.get("version") or exported.get("schema_name") or "unknown")
            title = supplied.get("title") or str(exported.get("name") or source.stem)
        raw = {
            "doc_id": supplied.get("doc_id") or f"file:{source.resolve()}",
            "title": title,
            "year": int(supplied.get("year", 0) or 0),
            "license": supplied.get("license", "unknown"),
            "local_path": str(source),
            "paragraphs": paragraphs,
            "tables": tables,
            "figures": figures,
            "metadata": {
                **supplied,
                "adapter": self.name,
                "parser": "docling",
                "parser_version": parser_version,
                "export_mode": export_mode,
            },
        }
        return DocumentPackage.from_dict(raw)


def _docling_texts(exported: dict[str, Any]) -> list[dict[str, Any]]:
    values = exported.get("texts") or exported.get("text_items") or []
    paragraphs: list[dict[str, Any]] = []
    for item in values:
        if not isinstance(item, dict):
            continue
        text = _first_nonempty(item, ("text", "content"))
        if not text:
            continue
        paragraphs.append({
            "id": f"p{len(paragraphs) + 1}",
            "page": _page_number(item),
            "text": text,
            "section": str(item.get("label") or item.get("type") or ""),
            "bbox": _bbox(item),
        })
    return paragraphs


def _docling_tables(exported: dict[str, Any]) -> list[dict[str, Any]]:
    values = exported.get("tables") or []
    tables: list[dict[str, Any]] = []
    for index, item in enumerate(values, 1):
        if not isinstance(item, dict):
            continue
        data = item.get("data") if isinstance(item.get("data"), dict) else item
        rows = _table_rows(data)
        if not rows:
            continue
        width = max(len(row) for row in rows)
        explicit_columns = data.get("columns")
        if not isinstance(explicit_columns, list):
            explicit_columns = item.get("columns")
        if isinstance(explicit_columns, list) and explicit_columns:
            headers = [str(cell or f"column_{column + 1}") for column, cell in enumerate(explicit_columns + [""] * width)][:width]
            body = rows
        else:
            if _has_header(data, rows):
                headers = [str(cell or f"column_{column + 1}") for column, cell in enumerate(rows[0] + [""] * width)][:width]
                body = rows[1:]
            else:
                headers = [f"column_{column + 1}" for column in range(width)]
                body = rows
        table_rows = [
            {headers[column]: row[column] if column < len(row) else "" for column in range(width)}
            for row in body
        ]
        tables.append({
            "id": str(item.get("label") or item.get("id") or f"Table {index}"),
            "page": _page_number(item),
            "caption": _first_nonempty(item, ("caption", "text")),
            "columns": headers,
            "rows": table_rows,
            "bbox": _bbox(item),
        })
    return tables


def _docling_figures(exported: dict[str, Any]) -> list[dict[str, Any]]:
    values = exported.get("pictures") or exported.get("figures") or []
    figures: list[dict[str, Any]] = []
    for index, item in enumerate(values, 1):
        if not isinstance(item, dict):
            continue
        alt_text = _first_nonempty(item, ("alt_text", "caption", "text", "description"))
        if not alt_text:
            continue
        figures.append({
            "id": str(item.get("id") or item.get("label") or f"fig{index}"),
            "label": str(item.get("label") or ""),
            "caption": str(item.get("caption") or ""),
            "alt_text": alt_text,
            "page": _page_number(item),
            "bbox": _bbox(item),
        })
    return figures


def _table_rows(data: dict[str, Any]) -> list[list[str]]:
    matrix = data.get("rows")
    if isinstance(matrix, list) and all(isinstance(row, list) for row in matrix):
        return [[str(cell or "") for cell in row] for row in matrix]
    cells = data.get("table_cells") or data.get("cells") or []
    if not isinstance(cells, list) or not cells:
        return []
    max_row = int(data.get("num_rows", 0) or 0)
    max_col = int(data.get("num_cols", 0) or 0)
    positions: list[tuple[int, int, str, int, int]] = []
    for cell in cells:
        if not isinstance(cell, dict):
            continue
        row = int(cell.get("start_row_offset_idx", cell.get("row", 0)) or 0)
        col = int(cell.get("start_col_offset_idx", cell.get("col", 0)) or 0)
        row_span = max(1, int(cell.get("row_span", 1) or 1))
        col_span = max(1, int(cell.get("col_span", 1) or 1))
        text = _first_nonempty(cell, ("text", "content"))
        positions.append((row, col, text, row_span, col_span))
        max_row = max(max_row, row + row_span)
        max_col = max(max_col, col + col_span)
    if not positions or max_row <= 0 or max_col <= 0:
        return []
    matrix = [[""] * max_col for _ in range(max_row)]
    for row, col, text, row_span, col_span in positions:
        for r in range(row, min(max_row, row + row_span)):
            for c in range(col, min(max_col, col + col_span)):
                matrix[r][c] = text
    return matrix


def _has_header(data: dict[str, Any], rows: list[list[str]]) -> bool:
    cells = data.get("table_cells") or data.get("cells") or []
    if any(isinstance(cell, dict) and cell.get("column_header") for cell in cells):
        return True
    # Prefer an explicit signal when a converter provides one. In particular,
    # do not infer a header merely because the first row is non-empty: layout
    # exports can omit ``column_header`` for tables whose first row is actual
    # data, and dropping it would silently lose a scientific measurement.
    for key in ("has_header", "header", "header_row"):
        if key in data and isinstance(data[key], bool):
            return data[key]
    if not rows or not rows[0]:
        return False
    first = " ".join(str(cell or "") for cell in rows[0]).casefold()
    # A conservative lexical fallback handles common unmarked header rows,
    # while leaving arbitrary text labels (which may be real sample IDs) in
    # the table as data.
    header_terms = (
        "sample", "compound", "cell line", "cell_line", "treatment", "assay",
        "ic50", "ec50", "value", "unit", "mean", "median", "error",
        "p-value", "p value", "dose", "concentration", "temperature", "yield",
        "response", "control",
    )
    return any(term in first for term in header_terms)


def _markdown_paragraphs(markdown: str) -> list[dict[str, Any]]:
    blocks = [block.strip() for block in re.split(r"\n\s*\n", markdown) if block.strip()]
    return [
        {"id": f"p{index}", "page": 0, "text": block}
        for index, block in enumerate(blocks, 1)
    ]


def _first_nonempty(item: dict[str, Any], keys: tuple[str, ...]) -> str:
    for key in keys:
        value = item.get(key)
        if value is not None and str(value).strip():
            return " ".join(str(value).split())
    return ""


def _page_number(item: dict[str, Any]) -> int:
    prov = item.get("prov")
    if isinstance(prov, list) and prov and isinstance(prov[0], dict):
        value = prov[0].get("page_no", prov[0].get("page", 0))
        try:
            return int(value or 0)
        except (TypeError, ValueError):
            return 0
    for key in ("page_no", "page"):
        try:
            return int(item.get(key, 0) or 0)
        except (TypeError, ValueError):
            continue
    return 0


def _bbox(item: dict[str, Any]) -> list[float] | None:
    prov = item.get("prov")
    candidate = prov[0] if isinstance(prov, list) and prov and isinstance(prov[0], dict) else item
    bbox = candidate.get("bbox") if isinstance(candidate, dict) else None
    if isinstance(bbox, dict):
        values = [bbox.get(key) for key in ("l", "b", "r", "t")]
    elif isinstance(bbox, (list, tuple)):
        values = list(bbox)
    else:
        return None
    try:
        return [float(value) for value in values]
    except (TypeError, ValueError):
        return None
