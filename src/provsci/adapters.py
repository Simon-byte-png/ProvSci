"""Input adapters that normalize common research files into DocumentPackage.

The core pipeline remains dependency-free. Rich PDF understanding can be
provided by Docling/GROBID/TATR in a future adapter, while this module gives
the project a useful local baseline for JSON, CSV, HTML, Markdown and text.
"""

from __future__ import annotations

import csv
from dataclasses import replace
import html
import json
import re
import subprocess
import zipfile
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Protocol, runtime_checkable
from xml.etree import ElementTree

from .models import DocumentPackage, InputError


class AdapterError(InputError):
    """Raised when an input file cannot be normalized."""


@runtime_checkable
class DocumentAdapter(Protocol):
    """Replaceable parser contract for layout-aware scientific documents.

    Docling, GROBID, TATR and Nougat integrations can implement this small
    interface and return the same ``DocumentPackage`` consumed by the mining
    and verifier stages.  The core package deliberately does not import any
    of those optional heavy dependencies.
    """

    name: str

    def supports(self, source: Path) -> bool:
        """Return whether this adapter can parse the local source."""

    def load(self, source: Path, metadata: dict[str, Any] | None = None) -> DocumentPackage:
        """Parse source into the stable intermediate document package."""


def load_document(
    path: str | Path,
    metadata: dict[str, Any] | None = None,
    adapter: DocumentAdapter | None = None,
) -> DocumentPackage:
    """Load one supported file and return the stable internal document form."""
    source = Path(path)
    if not source.exists():
        raise AdapterError(f"input file not found: {source}")
    if adapter is not None:
        try:
            supported = adapter.supports(source)
        except Exception as exc:  # pragma: no cover - third-party adapter boundary
            raise AdapterError(f"adapter {getattr(adapter, 'name', type(adapter).__name__)} failed supports(): {exc}") from exc
        if not supported:
            raise AdapterError(f"adapter {getattr(adapter, 'name', type(adapter).__name__)} does not support {source.suffix or '<no suffix>'}")
        try:
            parsed = adapter.load(source, metadata)
        except Exception as exc:  # pragma: no cover - third-party adapter boundary
            raise AdapterError(f"adapter {getattr(adapter, 'name', type(adapter).__name__)} failed to parse {source}: {exc}") from exc
        if isinstance(parsed, dict):
            parsed = DocumentPackage.from_dict(parsed)
        if not isinstance(parsed, DocumentPackage):
            raise AdapterError("custom adapter must return DocumentPackage or a document-package dictionary")
        adapter_name = str(getattr(adapter, "name", type(adapter).__name__))
        return replace(parsed, metadata={**parsed.metadata, "adapter": adapter_name})
    suffix = source.suffix.lower()
    if suffix == ".json":
        raw = json.loads(source.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise AdapterError("JSON document package must be an object")
        if metadata:
            raw = {
                **raw,
                **{key: value for key, value in metadata.items() if key in {"doc_id", "title", "year", "license", "local_path"}},
                "metadata": {**raw.get("metadata", {}), **metadata},
            }
        return DocumentPackage.from_dict(raw)
    if suffix in {".csv", ".tsv"}:
        return _from_delimited(source, "\t" if suffix == ".tsv" else ",", metadata)
    if suffix in {".html", ".htm"}:
        return _from_html(source, metadata)
    if suffix in {".xml", ".nxml"}:
        return _from_jats(source, metadata)
    if suffix in {".txt", ".md", ".markdown"}:
        return _from_text(source, metadata)
    if suffix == ".pdf":
        return _from_pdf(source, metadata)
    if suffix == ".xlsx":
        return _from_xlsx(source, metadata)
    raise AdapterError(f"unsupported input format: {suffix or '<none>'}")


def _base_metadata(source: Path, metadata: dict[str, Any] | None) -> dict[str, Any]:
    result = {
        "doc_id": f"file:{source.resolve()}",
        "title": source.stem,
        "year": 0,
        "license": "unknown",
    }
    result.update(metadata or {})
    result["local_path"] = str(source)
    return result


def _from_text(source: Path, metadata: dict[str, Any] | None) -> DocumentPackage:
    base = _base_metadata(source, metadata)
    text = source.read_text(encoding="utf-8", errors="replace")
    paragraphs = [
        {"id": f"p{index}", "page": 0, "text": block.strip()}
        for index, block in enumerate(re.split(r"\n\s*\n", text), 1)
        if block.strip()
    ]
    return DocumentPackage.from_dict({**base, "paragraphs": paragraphs, "metadata": {**(metadata or {}), "adapter": "text_v0.1"}})


def _from_delimited(source: Path, delimiter: str, metadata: dict[str, Any] | None) -> DocumentPackage:
    base = _base_metadata(source, metadata)
    with source.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle, delimiter=delimiter)
        if not reader.fieldnames:
            raise AdapterError("delimited file must contain a header row")
        rows = [dict(row) for row in reader]
    return DocumentPackage.from_dict({
        **base,
        "tables": [{
            "id": "Table 1",
            "page": 0,
            "caption": source.name,
            "columns": list(reader.fieldnames),
            "rows": rows,
        }],
        "metadata": {**(metadata or {}), "adapter": "delimited_v0.1"},
    })


class _HTMLDocumentParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.title_parts: list[str] = []
        self.paragraphs: list[str] = []
        self.tables: list[list[list[str]]] = []
        self._tag_stack: list[str] = []
        self._text: list[str] = []
        self._current_table: list[list[str]] | None = None
        self._current_row: list[str] | None = None
        self._in_title = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self._tag_stack.append(tag)
        if tag == "title":
            self._in_title = True
        if tag == "table":
            self._current_table = []
        if tag == "tr" and self._current_table is not None:
            self._current_row = []
        if tag in {"td", "th", "p", "h1", "h2", "h3", "caption"}:
            self._text = []

    def handle_data(self, data: str) -> None:
        if self._in_title:
            self.title_parts.append(data)
        self._text.append(data)

    def handle_endtag(self, tag: str) -> None:
        value = " ".join("".join(self._text).split())
        if tag == "title":
            self._in_title = False
        if tag in {"p", "h1", "h2", "h3"} and value:
            self.paragraphs.append(value)
        if tag in {"td", "th"} and self._current_row is not None:
            self._current_row.append(value)
        if tag == "tr" and self._current_table is not None and self._current_row:
            self._current_table.append(self._current_row)
            self._current_row = None
        if tag == "table" and self._current_table is not None:
            self.tables.append(self._current_table)
            self._current_table = None
        if self._tag_stack:
            self._tag_stack.pop()
        self._text = []


def _from_html(source: Path, metadata: dict[str, Any] | None) -> DocumentPackage:
    base = _base_metadata(source, metadata)
    parser = _HTMLDocumentParser()
    parser.feed(source.read_text(encoding="utf-8", errors="replace"))
    tables = []
    for index, matrix in enumerate(parser.tables, 1):
        if not matrix:
            continue
        width = max(len(row) for row in matrix)
        headers = [cell or f"column_{column + 1}" for column, cell in enumerate(matrix[0] + [""] * width)][:width]
        rows = [
            {headers[column]: row[column] if column < len(row) else "" for column in range(width)}
            for row in matrix[1:]
        ]
        tables.append({"id": f"Table {index}", "page": 0, "columns": headers, "rows": rows})
    if parser.title_parts:
        base["title"] = " ".join("".join(parser.title_parts).split())
    return DocumentPackage.from_dict({
        **base,
        "paragraphs": [{"id": f"p{index}", "page": 0, "text": text} for index, text in enumerate(parser.paragraphs, 1)],
        "tables": tables,
        "metadata": {**(metadata or {}), "adapter": "html_v0.1"},
    })


def _from_jats(source: Path, metadata: dict[str, Any] | None) -> DocumentPackage:
    """Normalize a PMC/JATS article, including paragraphs, tables and license."""
    try:
        root = ElementTree.parse(source).getroot()
    except ElementTree.ParseError as exc:
        raise AdapterError(f"could not parse JATS XML: {exc}") from exc

    base = _base_metadata(source, metadata)
    title = _first_text(root, ("article-title",))
    if title:
        base["title"] = title
    for node in root.iter():
        if _local_name(node.tag) != "article-id":
            continue
        id_type = node.attrib.get("pub-id-type", "").lower()
        value = _clean_text(node)
        if id_type == "pmcid" and value and not (metadata or {}).get("doc_id"):
            base["doc_id"] = value if value.startswith("PMC") else f"PMC{value}"
        elif id_type == "doi" and value:
            base["doi"] = value
            if not (metadata or {}).get("doc_id") and str(base.get("doc_id", "")).startswith("file:"):
                base["doc_id"] = f"doi:{value}"
        elif id_type == "pmid" and value:
            base["pmid"] = value

    year = _first_text(root, ("pub-date", "year")) or _first_text(root, ("year",))
    if year and year.isdigit() and not (metadata or {}).get("year"):
        base["year"] = int(year)

    if not (metadata or {}).get("license"):
        license_text = " ".join(
            _clean_text(node)
            for node in root.iter()
            if _local_name(node.tag) in {"license", "license-p"}
        ).strip()
        base["license"] = _normalize_license(license_text)

    parent_map = {child: parent for parent in root.iter() for child in parent}
    paragraphs = []
    for node in root.iter():
        if _local_name(node.tag) != "p" or _ancestor_is_table(root, node):
            continue
        value = _clean_text(node)
        if value:
            section_path = _section_path(node, parent_map)
            paragraphs.append({
                "id": f"p{len(paragraphs) + 1}",
                "page": 0,
                "text": value,
                "section": section_path[-1] if section_path else "",
                "section_path": section_path,
            })

    figures = []
    for figure in (node for node in root.iter() if _local_name(node.tag) == "fig"):
        alt_text = _first_text(figure, ("alt-text",))
        if not alt_text:
            continue
        figure_id = figure.attrib.get("id") or f"fig{len(figures) + 1}"
        section_path = _section_path(figure, parent_map)
        figures.append({
            "id": figure_id,
            "label": _first_text(figure, ("label",)),
            "caption": _first_text(figure, ("caption",)),
            "alt_text": alt_text,
            "section_path": section_path,
        })

    supplements = []
    for supplement in (node for node in root.iter() if _local_name(node.tag) == "supplementary-material"):
        supplement_id = supplement.attrib.get("id") or f"supp{len(supplements) + 1}"
        href = next((value for key, value in supplement.attrib.items() if key.rsplit("}", 1)[-1] == "href"), None)
        text = _clean_text(supplement)
        if not text and not href:
            continue
        supplements.append({
            "id": supplement_id,
            "label": _first_text(supplement, ("label",)),
            "caption": _first_text(supplement, ("caption",)),
            "href": href,
            "text": text,
            "section_path": _section_path(supplement, parent_map),
        })

    tables = []
    for wrap in (node for node in root.iter() if _local_name(node.tag) == "table-wrap"):
        table_node = next((node for node in wrap.iter() if _local_name(node.tag) == "table"), None)
        if table_node is None:
            continue
        header_rows = _jats_rows(table_node, "thead")
        body_rows = _jats_rows(table_node, "tbody")
        fallback_rows = _jats_rows(table_node, None) if not body_rows else []
        matrix = header_rows + body_rows if body_rows else fallback_rows
        if not matrix:
            continue
        width = max(len(row) for row in matrix)
        headers = _combine_jats_headers(table_node, width) if header_rows else [f"column_{index + 1}" for index in range(width)]
        headers = [(value or f"column_{index + 1}") for index, value in enumerate(headers + [""] * width)][:width]
        data_rows = matrix[len(header_rows):] if header_rows else matrix
        rows = [
            {headers[index]: row[index] if index < len(row) else "" for index in range(width)}
            for row in data_rows
        ]
        label = _first_text(wrap, ("label",)) or f"Table {len(tables) + 1}"
        caption = _first_text(wrap, ("caption",))
        tables.append({
            "id": label,
            "page": 0,
            "caption": caption,
            "columns": headers,
            "rows": rows,
            "section_path": _section_path(wrap, parent_map),
        })

    return DocumentPackage.from_dict({
        **base,
        "paragraphs": paragraphs,
        "tables": tables,
        "figures": figures,
        "supplements": supplements,
        # Keep identifiers recovered from the article header (DOI/PMID/PMCID)
        # in metadata as well as in the DocumentPackage fields.  Source
        # acquisition uses this metadata to build a manifest without forcing
        # callers to re-parse the XML.
        "metadata": {**base, **(metadata or {}), "adapter": "jats_v0.1"},
    })


def _local_name(tag: object) -> str:
    return str(tag).rsplit("}", 1)[-1]


def _clean_text(node: ElementTree.Element) -> str:
    return html.unescape(" ".join("".join(node.itertext()).split()))


def _first_text(root: ElementTree.Element, path: tuple[str, ...]) -> str:
    target = path[-1]
    for node in root.iter():
        if _local_name(node.tag) == target:
            value = _clean_text(node)
            if value:
                return value
    return ""


def _ancestor_is_table(root: ElementTree.Element, target: ElementTree.Element) -> bool:
    # ElementTree has no parent pointers; table cell paragraphs are ignored by
    # identity search to avoid mining the same value as table and text evidence.
    for wrap in (node for node in root.iter() if _local_name(node.tag) == "table-wrap"):
        if any(node is target for node in wrap.iter()):
            return True
    return False


def _section_path(
    node: ElementTree.Element,
    parent_map: dict[ElementTree.Element, ElementTree.Element],
) -> list[str]:
    path: list[str] = []
    parent = parent_map.get(node)
    while parent is not None:
        if _local_name(parent.tag) in {"sec", "abstract"}:
            title = next(
                (_clean_text(child) for child in parent if _local_name(child.tag) == "title"),
                "Abstract" if _local_name(parent.tag) == "abstract" else "",
            )
            if title:
                path.append(title)
        parent = parent_map.get(parent)
    return list(reversed(path))


def _jats_rows(table: ElementTree.Element, section_name: str | None) -> list[list[str]]:
    sections = [table]
    if section_name:
        sections = [node for node in table.iter() if _local_name(node.tag) == section_name]
    rows = []
    for section in sections:
        for row in section.iter():
            if _local_name(row.tag) != "tr":
                continue
            cells = [
                _clean_text(cell)
                for cell in row
                if _local_name(cell.tag) in {"td", "th"}
            ]
            if cells:
                rows.append(cells)
    return rows


def _combine_jats_headers(table: ElementTree.Element, width: int) -> list[str]:
    thead = next((node for node in table.iter() if _local_name(node.tag) == "thead"), None)
    if thead is None:
        return [f"column_{index + 1}" for index in range(width)]
    rows = [node for node in thead.iter() if _local_name(node.tag) == "tr"]
    grid: list[list[str]] = [[""] * width for _ in rows]
    for row_index, row in enumerate(rows):
        column = 0
        for cell in row:
            if _local_name(cell.tag) not in {"td", "th"}:
                continue
            while column < width and grid[row_index][column]:
                column += 1
            value = _clean_text(cell)
            colspan = int(cell.attrib.get("colspan", "1"))
            rowspan = int(cell.attrib.get("rowspan", "1"))
            for row_offset in range(max(1, rowspan)):
                target_row = row_index + row_offset
                if target_row >= len(grid):
                    break
                for col_offset in range(max(1, colspan)):
                    target_col = column + col_offset
                    if target_col < width:
                        grid[target_row][target_col] = value
            column += max(1, colspan)
    if not grid:
        return [f"column_{index + 1}" for index in range(width)]
    headers = []
    for index in range(width):
        parts = []
        for row in grid:
            value = row[index]
            if value and value not in parts:
                parts.append(value)
        headers.append(" / ".join(parts) or f"column_{index + 1}")
    return headers


def _normalize_license(text: str) -> str:
    value = text.casefold()
    if "cc0" in value or "public domain" in value:
        return "public-domain"
    if "creative commons attribution-noncommercial-sharealike" in value or "cc by-nc-sa" in value:
        return "CC-BY-NC-SA"
    if "creative commons attribution-noncommercial" in value or "cc by-nc" in value:
        return "CC-BY-NC"
    if "creative commons attribution-sharealike" in value or "cc by-sa" in value:
        return "CC-BY-SA-4.0"
    if "creative commons attribution" in value or "cc by" in value:
        return "CC-BY-4.0"
    return "unknown"


def _from_pdf(source: Path, metadata: dict[str, Any] | None) -> DocumentPackage:
    """Use pdftotext when available; rich layout stays an optional adapter."""
    try:
        result = subprocess.run(
            ["pdftotext", "-layout", str(source), "-"],
            check=True,
            capture_output=True,
            text=True,
        )
    except (FileNotFoundError, subprocess.CalledProcessError) as exc:
        raise AdapterError(
            "PDF input needs pdftotext or an optional Docling/GROBID adapter; "
            "install a parser and normalize its output to DocumentPackage"
        ) from exc
    base = _base_metadata(source, metadata)
    paragraphs = []
    for page_number, page_text in enumerate(result.stdout.split("\f"), 1):
        for block in re.split(r"\n\s*\n", page_text):
            if block.strip():
                paragraphs.append({
                    "id": f"p{len(paragraphs) + 1}",
                    "page": page_number,
                    "text": block.strip(),
                    "section_path": [],
                })
    return DocumentPackage.from_dict({
        **base,
        "paragraphs": paragraphs,
        "metadata": {
            **(metadata or {}),
            "adapter": "pdftotext_v0.2",
            "parser_version": "pdftotext",
            "page_count": len(result.stdout.split("\f")),
            "layout_preserved": True,
        },
    })


def _from_xlsx(source: Path, metadata: dict[str, Any] | None) -> DocumentPackage:
    """Read the first worksheet with stdlib XML for a lightweight baseline."""
    base = _base_metadata(source, metadata)
    try:
        with zipfile.ZipFile(source) as archive:
            shared = []
            if "xl/sharedStrings.xml" in archive.namelist():
                root = ElementTree.fromstring(archive.read("xl/sharedStrings.xml"))
                ns = {"x": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
                shared = ["".join(node.itertext()) for node in root.findall("x:si", ns)]
            workbook = ElementTree.fromstring(archive.read("xl/workbook.xml"))
            rels = ElementTree.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
            ns = {"x": "http://schemas.openxmlformats.org/spreadsheetml/2006/main", "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships"}
            rel_ns = {"r": "http://schemas.openxmlformats.org/package/2006/relationships"}
            first = workbook.find("x:sheets/x:sheet", ns)
            if first is None:
                raise AdapterError("xlsx has no worksheet")
            relation_id = first.attrib.get("{" + ns["r"] + "}id")
            target = next((item.attrib.get("Target") for item in rels if item.attrib.get("Id") == relation_id), None)
            if not target:
                raise AdapterError("xlsx worksheet relationship missing")
            worksheet_path = "xl/" + target.lstrip("/") if not target.startswith("xl/") else target
            sheet = ElementTree.fromstring(archive.read(worksheet_path))
            rows = []
            for row in sheet.findall("x:sheetData/x:row", ns):
                values = []
                for cell in row.findall("x:c", ns):
                    value = cell.find("x:v", ns)
                    text = value.text if value is not None and value.text is not None else ""
                    if cell.attrib.get("t") == "s" and text.isdigit():
                        text = shared[int(text)]
                    values.append(text)
                rows.append(values)
    except (KeyError, zipfile.BadZipFile, ElementTree.ParseError, ValueError) as exc:
        raise AdapterError(f"could not parse xlsx: {exc}") from exc
    if not rows:
        raise AdapterError("xlsx worksheet is empty")
    width = max(len(row) for row in rows)
    headers = [value or f"column_{index + 1}" for index, value in enumerate(rows[0] + [""] * width)][:width]
    table_rows = [{headers[index]: row[index] if index < len(row) else "" for index in range(width)} for row in rows[1:]]
    return DocumentPackage.from_dict({
        **base,
        "tables": [{"id": "Table 1", "page": 0, "columns": headers, "rows": table_rows}],
        "metadata": {**(metadata or {}), "adapter": "xlsx_stdlib_v0.1"},
    })
