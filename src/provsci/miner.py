"""Candidate mining for the first, table-centric vertical slice."""

from __future__ import annotations

import hashlib
import re
from typing import Any, Iterator

from .models import Candidate, DocumentPackage
from .path import extract_relation_claim
from .values import extract_measurement_occurrences, parse_measurement, parse_number_unit


def _safe_id(doc_id: str, table_id: str, row_key: str, column: str) -> str:
    digest = hashlib.sha1(f"{doc_id}|{table_id}|{row_key}|{column}".encode()).hexdigest()[:10]
    return f"provscicandidate-{digest}"


def _row_label(row: dict[str, Any], index: int) -> str:
    for key in ("Sample", "sample", "Cell line", "cell line", "cell_line", "Compound", "compound", "Name", "name", "id"):
        if row.get(key) not in (None, ""):
            return str(row[key])
    return f"row {index + 1}"


def _subject(document: DocumentPackage) -> str:
    value = document.metadata.get("subject") or document.metadata.get("domain")
    return str(value or "scientific_data")


def _column_default_unit(column: str) -> str:
    match = re.search(r"(?:\(|/|\s)(%|°?[A-Za-zμµ]+(?:/[A-Za-zμµ]+)?)\)?", column)
    return match.group(1) if match else ""


def _column_metric(column: str, caption: str = "") -> str:
    context = f"{column} {caption}".casefold()
    if "ic50" in context:
        return "IC50"
    if "mean" in context:
        return "mean"
    if "standard error" in context or "error" in context:
        return "standard error"
    if "p-value" in context or "p value" in context:
        return "p-value"
    if "viability" in context:
        return "cell viability"
    if "response" in context:
        return "response"
    return str(column)


def mine_numeric_table_candidates(document: DocumentPackage) -> Iterator[Candidate]:
    """Turn parseable table cells into auditable numeric QA candidates."""
    for table in document.tables:
        table_id = str(table.get("id", ""))
        page = int(table.get("page", 0))
        for row_index, row in enumerate(table.get("rows", [])):
            row_key = _row_label(row, row_index)
            for column, raw_value in row.items():
                if column.lower() in {"sample", "compound", "name", "id"}:
                    continue
                try:
                    default_unit = str(table.get("column_units", {}).get(column, "")) or _column_default_unit(str(column))
                    measurement = parse_measurement(raw_value, default_unit)
                    normalized = f"{measurement['value']} {measurement['unit']}" if measurement["unit"] else measurement["value"]
                    parsed = parse_number_unit(normalized)
                except ValueError:
                    continue
                display = str(raw_value).strip()
                metric = _column_metric(str(column), str(table.get("caption", "")))
                condition = str(column).split(" / ", 1)[1] if " / " in str(column) else None
                evidence = [{
                    "modality": "table",
                    "locator": {
                        "page": page,
                        "table_id": table_id,
                        "row": row_key,
                        "row_index": row_index,
                        "col": str(column),
                    },
                    "span_text": display,
                }]
                path = [
                    {
                        "step_id": 1,
                        "action": "extract_table_cell",
                        "tool": "table_parser",
                        "args": {
                            "page": page,
                            "table_id": table_id,
                            "row_key": row_key,
                            "row_index": row_index,
                            "col": str(column),
                        },
                        "output": display,
                        "depends_on": [],
                    },
                    {
                        "step_id": 2,
                        "action": "parse_measurement",
                        "tool": "number_unit_parser",
                        "args": {"value_from": 1, "default_unit": default_unit},
                        "output": {"value": parsed.value, "unit": parsed.unit, "uncertainty": measurement.get("uncertainty")},
                        "depends_on": [1],
                    },
                ]
                candidate_id = _safe_id(document.doc_id, table_id, row_key, str(column))
                yield Candidate(
                    candidate_id=candidate_id,
                    doc_id=document.doc_id,
                    subject=_subject(document),
                    task_type="numeric_qa",
                    question=(
                        f"What {metric} was reported for {row_key}"
                        + (f" under {condition}" if condition else "")
                        + "?"
                    ),
                    answer={
                        "value": parsed.value,
                        "unit": parsed.unit,
                        "display": display,
                        "uncertainty": measurement.get("uncertainty"),
                        "metric": metric,
                        "entity": row_key,
                        "condition": condition,
                    },
                    evidence=evidence,
                    acquisition_path=path,
                    page_span=[page],
                )


def mine_text_relations(document: DocumentPackage) -> Iterator[Candidate]:
    """Find a small, explicit comparison pattern for early failure analysis.

    This deliberately emits no Gold-ready path yet: a relation needs a
    structured claim extractor before it can be verified deterministically.
    """
    for paragraph in document.paragraphs:
        text = str(paragraph.get("text", ""))
        try:
            relation_claim = extract_relation_claim(text)
        except ValueError:
            continue
        page = int(paragraph.get("page", 0))
        verb = relation_claim["value"]
        subject = relation_claim["subject"]
        object_text = relation_claim["object"]
        paragraph_id = str(paragraph.get("id"))
        yield Candidate(
            candidate_id=_safe_id(document.doc_id, "paragraph", str(paragraph.get("id")), "relation"),
            doc_id=document.doc_id,
            subject=_subject(document),
            task_type="relation",
            question=f"What relationship is reported between {subject} and {object_text}?",
            answer=relation_claim,
            evidence=[{
                "modality": "text",
                "locator": {"page": page, "paragraph_id": str(paragraph.get("id"))},
                "span_text": text,
            }],
            acquisition_path=[
                {
                    "step_id": 1,
                    "action": "read_text_span",
                    "tool": "text_parser",
                    "args": {"paragraph_id": paragraph_id, "page": page},
                    "output": text,
                    "depends_on": [],
                },
                {
                    "step_id": 2,
                    "action": "extract_relation",
                    "tool": "relation_parser",
                    "args": {
                        "text_from": 1,
                        "relation": verb,
                        "subject": subject,
                        "object": object_text,
                    },
                    "output": relation_claim,
                    "depends_on": [1],
                },
            ],
            page_span=[page],
        )


def mine_numeric_text_candidates(document: DocumentPackage) -> Iterator[Candidate]:
    """Mine unit-bearing numbers from result paragraphs with a replayable span."""
    for paragraph in document.paragraphs:
        paragraph_id = str(paragraph.get("id"))
        text = str(paragraph.get("text", ""))
        page = int(paragraph.get("page", 0))
        for match_index, (start, end, parsed, uncertainty) in enumerate(extract_measurement_occurrences(text)):
            display = text[start:end].strip()
            question, metric, entity = _numeric_question(text, start, end, paragraph_id, parsed.unit)
            yield Candidate(
                candidate_id=_safe_id(document.doc_id, "paragraph", paragraph_id, f"number-{match_index}"),
                doc_id=document.doc_id,
                subject=_subject(document),
                task_type="numeric_qa",
                question=question,
                answer={
                    "value": parsed.value,
                    "unit": parsed.unit,
                    "display": display,
                    "uncertainty": uncertainty,
                    "metric": metric,
                    "entity": entity,
                },
                evidence=[{
                    "modality": "text",
                    "locator": {"page": page, "paragraph_id": paragraph_id, "char_span": [start, end]},
                    "span_text": display,
                }],
                acquisition_path=[
                    {
                        "step_id": 1,
                        "action": "read_text_span",
                        "tool": "text_parser",
                        "args": {"paragraph_id": paragraph_id, "page": page},
                        "output": text,
                        "depends_on": [],
                    },
                    {
                        "step_id": 2,
                        "action": "extract_number_unit",
                        "tool": "number_unit_parser",
                        "args": {"text_from": 1, "match_index": match_index},
                        "output": {"value": parsed.value, "unit": parsed.unit, "span_text": display, "uncertainty": uncertainty},
                        "depends_on": [1],
                    },
                ],
                page_span=[page],
            )


def mine_figure_numeric_candidates(document: DocumentPackage) -> Iterator[Candidate]:
    """Mine numeric claims from figure alt-text with figure-level provenance."""
    for figure in document.figures:
        figure_id = str(figure.get("id"))
        text = str(figure.get("alt_text", ""))
        for match_index, (start, end, parsed, uncertainty) in enumerate(extract_measurement_occurrences(text)):
            display = text[start:end].strip()
            question, metric, entity = _numeric_question(text, start, end, figure_id, parsed.unit)
            yield Candidate(
                candidate_id=_safe_id(document.doc_id, "figure", figure_id, f"number-{match_index}"),
                doc_id=document.doc_id,
                subject=_subject(document),
                task_type="numeric_qa",
                question=question,
                answer={
                    "value": parsed.value,
                    "unit": parsed.unit,
                    "display": display,
                    "uncertainty": uncertainty,
                    "metric": metric,
                    "entity": entity,
                },
                evidence=[{
                    "modality": "figure",
                    "locator": {"figure_id": figure_id, "char_span": [start, end]},
                    "span_text": display,
                }],
                acquisition_path=[
                    {
                        "step_id": 1,
                        "action": "read_figure_alt_text",
                        "tool": "figure_parser",
                        "args": {"figure_id": figure_id},
                        "output": text,
                        "depends_on": [],
                    },
                    {
                        "step_id": 2,
                        "action": "extract_number_unit",
                        "tool": "number_unit_parser",
                        "args": {"text_from": 1, "match_index": match_index},
                        "output": {"value": parsed.value, "unit": parsed.unit, "span_text": display, "uncertainty": uncertainty},
                        "depends_on": [1],
                    },
                ],
                page_span=[0],
            )


def _numeric_question(
    text: str,
    start: int,
    end: int,
    paragraph_id: str,
    unit: str,
) -> tuple[str, str, str | None]:
    prefix = text[max(0, start - 600):start]
    suffix = text[end:min(len(text), end + 140)]
    metric = "numeric result"
    metric_rules = (
        (r"IC\s*50", "IC50"),
        (r"cell viability reduction", "cell viability reduction"),
        (r"viability", "cell viability"),
        (r"response", "response"),
        (r"yield", "yield"),
        (r"accuracy", "accuracy"),
        (r"concentration", "concentration"),
    )
    best_distance: int | None = None
    explicit_metric: tuple[int, str] | None = None
    for pattern, label in metric_rules:
        if label in {"IC50", "cell viability reduction", "cell viability"}:
            for match in re.finditer(pattern, prefix, re.IGNORECASE):
                distance = len(prefix) - match.end()
                if explicit_metric is None or distance < explicit_metric[0]:
                    explicit_metric = (distance, label)
    if explicit_metric is not None:
        metric = explicit_metric[1]
        best_distance = explicit_metric[0]
    if unit in {"h", "min", "s", "ms"}:
        metric = "treatment duration"
        best_distance = 0
    elif explicit_metric is None and unit in {"μM", "uM", "nM", "pM", "mM", "M", "mg/mL", "μg/mL", "ug/mL", "ng/mL", "U/ml", "U/mL"}:
        if re.search(r"(?:concentrations?|treated|cultured|incubated|stock|dose|dilut|at\s+the)\b", prefix, re.IGNORECASE):
            metric = "treatment concentration"
            best_distance = 0
    for pattern, label in metric_rules:
        if best_distance == 0 or explicit_metric is not None:
            break
        for match in re.finditer(pattern, prefix, re.IGNORECASE):
            distance = len(prefix) - match.end()
            if best_distance is None or distance < best_distance:
                best_distance = distance
                metric = label
    if metric == "numeric result" and unit in {"C", "°C", "K"}:
        metric = "temperature"

    if re.search(r"(?:proportion|percentage|percent|rate)\s+of\s+(?:early\s+|late\s+)?apoptosis", prefix, re.IGNORECASE):
        metric = "apoptosis proportion"
    elif re.search(r"(?:proportion|percentage|percent)\s+of\s+(?:the\s+)?[SGG0-9/→-]+\s*phase", prefix, re.IGNORECASE):
        metric = "cell-cycle proportion"

    entity = None
    after = re.match(
        r"\s*(?:of\s+(?:the\s+)?control\)?\s*)?(?:was\s+|were\s+)?for\s+([^;,.()]+)",
        suffix,
        re.IGNORECASE,
    )
    if after:
        entity = " ".join(after.group(1).split()).strip()
    if not entity:
        concentration_entity = re.search(r"concentrations?\s+of\s+([A-Za-z0-9][A-Za-z0-9 -]{1,50})", prefix, re.IGNORECASE)
        if concentration_entity:
            entity = " ".join(concentration_entity.group(1).split()).strip()
            entity = re.split(r"\s+(?:to|for|and|were|was)\s+", entity, maxsplit=1, flags=re.IGNORECASE)[0]
    if not entity:
        metric_before = re.search(
            r"([^.;]{2,100}?)\s+(?:alone\s+)?(?:had|has|showed|reported)?\s*(?:an?\s+)?"
            r"(?:IC\s*50|viability|response|yield)\s+(?:of|was|were)\s*$",
            prefix,
            re.IGNORECASE,
        )
        if metric_before:
            entity = " ".join(metric_before.group(1).split()).strip()
            if "," in entity:
                entity = entity.rsplit(",", 1)[-1].strip()
    if not entity:
        before = re.search(
            r"([^.;]{3,140}?)\s*\(\s*(?:viability|response|yield|IC\s*50)\s*$",
            prefix,
            re.IGNORECASE,
        )
        if before:
            entity = " ".join(before.group(1).split()).strip()
            for separator in (";", ".", " than "):
                if separator in entity:
                    entity = entity.rsplit(separator, 1)[-1].strip()
            entity = re.sub(
                r"^(?:and\s+)?(?:was\s+)?(?:comparable\s+to\s+|more\s+effective\s+than\s+)?(?:the\s+)?(?:combination\s+of\s+)?",
                "",
                entity,
                flags=re.IGNORECASE,
            )
    if not entity:
        # Domain-specific identifiers are safer than guessing arbitrary nouns
        # from a long sentence. This covers common cell-line/result contexts.
        identifiers = list(re.finditer(r"\b(?:SW\d+|HT-?\d+|Hs\d+|MCF-?\d+|HCT\d+)\b", prefix))
        if identifiers:
            entity = identifiers[-1].group(0)
    if entity:
        return f"What {metric} was reported for {entity}?", metric, entity
    return f"What {metric} is reported in paragraph {paragraph_id}?", metric, None


_RESULT_SECTION_TERMS = (
    "result", "finding", "outcome", "efficacy", "cytotoxicity", "activity", "performance", "evaluation",
)
_METHOD_SECTION_TERMS = (
    "method", "material", "reagent", "culture", "protocol", "statistical", "production", "treatment",
)
_RESULT_TEXT_TERMS = (
    "ic50", "viability", "yield", "response", "reduction", "increase", "decrease", "higher", "lower",
    "significant", "efficacy", "fold", "correlated", "accuracy", "error", "performance",
)


def is_result_paragraph(paragraph: dict[str, Any]) -> bool:
    """Conservative section-aware router for result claims.

    Documents without section metadata remain eligible so normalized JSON/HTML
    fixtures and plain text can still run; rich JATS inputs use section gates.
    """
    section_path = " ".join(str(item) for item in paragraph.get("section_path", [])).casefold()
    text = str(paragraph.get("text", "")).casefold()
    if section_path:
        if any(term in section_path for term in _METHOD_SECTION_TERMS):
            return False
        return any(term in section_path for term in _RESULT_SECTION_TERMS)
    return any(term in text for term in _RESULT_TEXT_TERMS)


def is_core_result_candidate(candidate: Candidate) -> bool:
    """Separate outcome values from experimental conditions in result prose."""
    answer = candidate.answer
    if candidate.task_type == "numeric_qa":
        if answer.get("metric") in {"treatment duration", "treatment concentration", "temperature", "time"}:
            return False
        if answer.get("metric") == "numeric result":
            return False
    return True
