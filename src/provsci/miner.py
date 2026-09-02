"""Candidate mining for the first, table-centric vertical slice."""

from __future__ import annotations

import hashlib
import re
from typing import Any, Iterator

from .models import Candidate, DocumentPackage
from .path import extract_relation_claim
from .profile import resolve_domain
from .values import extract_measurement_occurrences, parse_measurement, parse_number_unit
from .figures import figure_axis, iter_figure_points, point_display, point_x_display, point_value_for_path


# JATS and PDF text frequently use typographic hyphens for cell-line and
# compound names (for example ``MDA‐MB‐231``). These characters are
# single-codepoint substitutions, so normalising them preserves the character
# offsets used by evidence locators while making semantic matching stable.
_SEMANTIC_TRANSLATION = str.maketrans({
    "‐": "-",
    "‑": "-",
    "‒": "-",
    "–": "-",
    "—": "-",
    "−": "-",
    "µ": "μ",
})
_CELL_LINE_PATTERN = r"(?:SW\d+|HT-?\d+|Hs\d+|MCF-?\d+|HCT\d+|MDA-MB-?\d+)"


def _semantic_text(text: str) -> str:
    """Return matching-friendly text without changing its length."""
    return text.translate(_SEMANTIC_TRANSLATION)


def _local_clause(text: str, limit: int = 520) -> str:
    """Return the current sentence without splitting on decimal points."""
    clauses = re.split(r"(?<=[.!?])\s+", text)
    return clauses[-1][-limit:]


def _safe_id(doc_id: str, table_id: str, row_key: str, column: str) -> str:
    digest = hashlib.sha1(f"{doc_id}|{table_id}|{row_key}|{column}".encode()).hexdigest()[:10]
    return f"provscicandidate-{digest}"


def _clean_entity(value: str | None) -> str | None:
    """Trim reporting verbs accidentally captured as part of a sample label."""
    if not value:
        return value
    cleaned = " ".join(str(value).split()).strip(" ,.;:")
    if re.match(r"^(?:sample|batch|group|specimen|material|run|trial|condition)\b", cleaned, re.IGNORECASE):
        cleaned = re.sub(
            r"\s+(?:achieved|reached|reported|showed|had|gave|yielded|was|were|is|are|"
            r"tested|measured|recorded|observed|under|at|for|with)\b.*$",
            "",
            cleaned,
            flags=re.IGNORECASE,
        ).strip(" ,.;:")
    return cleaned or None


def _row_label(row: dict[str, Any], index: int) -> str:
    for key in (
        "Sample", "sample", "Sample ID", "sample_id", "Cell line", "cell line", "cell_line",
        "Compound", "compound", "Batch", "batch", "Group", "group", "Specimen", "specimen",
        "Material", "material", "Treatment", "treatment", "Condition", "condition",
        "Name", "name", "Analyte", "analyte", "hPMTs", "hPMT", "PTM", "ptm", "id",
    ):
        if row.get(key) not in (None, ""):
            return str(row[key])
    return f"row {index + 1}"


def _subject(document: DocumentPackage) -> str:
    value = document.metadata.get("subject") or resolve_domain(document.metadata)
    return str(value or "scientific_data")


def _column_default_unit(column: str) -> str:
    match = re.search(r"(?:\(|/|\s)(%|°?[A-Za-zμµ]+(?:/[A-Za-zμµ]+)?)\)?", column)
    return match.group(1) if match else ""


def _column_metric(column: str, caption: str = "") -> str:
    column_text = str(column).casefold()
    caption_text = str(caption).casefold()
    context = f"{column_text} {caption_text}"
    # Column-local semantics take precedence over caption-wide wording.  A
    # caption can mention "IC50", "mean" or "standard error" while the
    # current column represents a different statistic.
    if "p-value" in column_text or "p value" in column_text:
        return "p-value"
    if "standard error" in column_text or "error" in column_text:
        return "standard error"
    if "mean" in column_text:
        return "mean"
    if "ic50" in column_text:
        return "IC50"
    if re.search(r"\b(?:temperature|temp)\b", column_text):
        return "temperature"
    if "pressure" in column_text:
        return "pressure"
    if re.search(r"\b(?:duration|time)\b", column_text):
        return "duration"
    if "yield" in column_text:
        return "yield"
    if "purity" in column_text:
        return "purity"
    if "efficien" in column_text:
        return "efficiency"
    if "intensity" in column_text:
        return "intensity"
    if "viability" in column_text:
        return "cell viability"
    if "response" in column_text:
        return "response"
    # Caption fallback is used only when the column header is generic (for
    # example ``Value`` or ``Result``).
    if "ic50" in context:
        return "IC50"
    if re.search(r"\b(?:temperature|temp)\b", context):
        return "temperature"
    if "pressure" in context:
        return "pressure"
    if re.search(r"\b(?:duration|time)\b", context):
        return "duration"
    if "yield" in context:
        return "yield"
    if "purity" in context:
        return "purity"
    if "efficien" in context:
        return "efficiency"
    if "intensity" in context:
        return "intensity"
    if "viability" in context:
        return "cell viability"
    if "response" in context:
        return "response"
    return str(column)


def _caption_condition(caption: str) -> str | None:
    """Extract a clearly stated global duration from a table caption.

    This is deliberately conservative: only an explicit number followed by a
    supported time unit and introduced by common experimental wording is
    propagated to every cell.  Ambiguous values remain ``not_extracted``.
    """
    match = re.search(
        r"\b(?:after|for|at|incubated|collected)\s+(\d+(?:\.\d+)?)\s*(ms|s|min|h|day|d)\b",
        str(caption),
        flags=re.IGNORECASE,
    )
    return f"{match.group(1)} {match.group(2)}" if match else None


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
                header_condition = str(column).split(" / ", 1)[1] if " / " in str(column) else None
                # A slash suffix is a condition only when it looks like an
                # explicit time value (e.g. ``IC50 / 24 h``). Headers such as
                # ``Mean / Hs27`` encode a comparison group, not duration.
                if header_condition and not re.match(r"^\s*\d+(?:\.\d+)?\s*(?:ms|s|min|h|day|d)\s*$", header_condition, re.IGNORECASE):
                    header_condition = None
                condition = header_condition
                condition_fields: dict[str, str] = {}
                condition_source = "column_header" if condition is not None else None
                if condition is None:
                    caption_condition = _caption_condition(str(table.get("caption", "")))
                    if caption_condition:
                        condition = caption_condition
                        condition_source = "table_caption"
                        condition_fields["exposure_time_or_duration"] = caption_condition
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
                        "condition_source": condition_source,
                        "condition_fields": condition_fields,
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
            condition, condition_fields = _infer_conditions(text, start, end, entity)
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
                    "condition": condition,
                    "condition_fields": condition_fields,
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
    """Mine numeric claims from figure alt-text or structured curve points."""
    for figure in document.figures:
        figure_id = str(figure.get("id"))
        text = str(figure.get("alt_text", ""))
        for match_index, (start, end, parsed, uncertainty) in enumerate(extract_measurement_occurrences(text)):
            display = text[start:end].strip()
            question, metric, entity = _numeric_question(text, start, end, figure_id, parsed.unit)
            condition, condition_fields = _infer_conditions(text, start, end, entity)
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
                    "condition": condition,
                    "condition_fields": condition_fields,
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
        # Layout adapters or a user-provided package may expose explicit
        # curve/bar points.  These are safe to replay because the point index
        # and axis units are part of the locator/path; image-only figures are
        # still handled by the conservative alt-text branch above.
        x_axis = figure_axis(figure, "x")
        y_axis = figure_axis(figure, "y")
        for point in iter_figure_points(figure):
            display = point_display(point, y_axis)
            if not display:
                continue
            try:
                measurement = parse_measurement(display, str(y_axis.get("unit", "")))
                parsed = parse_number_unit(f"{measurement['value']} {measurement['unit']}" if measurement["unit"] else measurement["value"])
            except (TypeError, ValueError):
                continue
            entity = point["series_name"]
            metric = _column_metric(str(y_axis.get("label", "y")), str(figure.get("caption", "")))
            x_display = point_x_display(point, x_axis)
            condition = f"{x_axis.get('label', 'x')}={x_display}" if x_display else None
            condition_fields: dict[str, str] = {}
            if x_display:
                label = str(x_axis.get("label", "")).casefold()
                if x_axis.get("unit") in {"ms", "s", "min", "h", "day", "d"} or any(term in label for term in ("time", "duration", "hour", "day")):
                    condition_fields["exposure_time_or_duration"] = x_display
                else:
                    condition_fields["context"] = f"{x_axis.get('label', 'x')}={x_display}"
            locator = {
                "figure_id": figure_id,
                "series_index": point["series_index"],
                "series": point["series_name"],
                "point_index": point["point_index"],
                "x": point["x"],
                "y_axis": str(y_axis.get("label", "y")),
            }
            yield Candidate(
                candidate_id=_safe_id(document.doc_id, "figure", figure_id, f"series-{point['series_index']}-point-{point['point_index']}"),
                doc_id=document.doc_id,
                subject=_subject(document),
                task_type="numeric_qa",
                question=f"What {metric} was reported for {entity}" + (f" at {x_display}" if x_display else "") + "?",
                answer={
                    "value": parsed.value,
                    "unit": parsed.unit,
                    "display": display,
                    "uncertainty": measurement.get("uncertainty"),
                    "metric": metric,
                    "entity": entity,
                    "condition": condition,
                    "condition_source": "figure_axis",
                    "condition_fields": condition_fields,
                },
                evidence=[{"modality": "figure", "locator": locator, "span_text": display}],
                acquisition_path=[
                    {
                        "step_id": 1,
                        "action": "extract_figure_point",
                        "tool": "figure_parser",
                        "args": {
                            "figure_id": figure_id,
                            "series_index": point["series_index"],
                            "point_index": point["point_index"],
                            "value_axis": "y",
                        },
                        "output": point_value_for_path(point, y_axis),
                        "depends_on": [],
                    },
                    {
                        "step_id": 2,
                        "action": "parse_measurement",
                        "tool": "number_unit_parser",
                        "args": {"value_from": 1, "default_unit": str(y_axis.get("unit", ""))},
                        "output": {"value": parsed.value, "unit": parsed.unit, "uncertainty": measurement.get("uncertainty")},
                        "depends_on": [1],
                    },
                ],
                page_span=[int(figure.get("page", 0) or 0)],
            )


def mine_supplement_numeric_candidates(document: DocumentPackage) -> Iterator[Candidate]:
    """Mine unit-bearing values from inline JATS supplementary material."""
    for supplement in document.supplements:
        supplement_id = str(supplement.get("id"))
        text = str(supplement.get("text", ""))
        if not text:
            continue
        for match_index, (start, end, parsed, uncertainty) in enumerate(extract_measurement_occurrences(text)):
            display = text[start:end].strip()
            question, metric, entity = _numeric_question(text, start, end, supplement_id, parsed.unit)
            condition, condition_fields = _infer_conditions(text, start, end, entity)
            yield Candidate(
                candidate_id=_safe_id(document.doc_id, "supplement", supplement_id, f"number-{match_index}"),
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
                    "condition": condition,
                    "condition_fields": condition_fields,
                },
                evidence=[{
                    "modality": "supplement",
                    "locator": {"supplement_id": supplement_id, "char_span": [start, end]},
                    "span_text": display,
                }],
                acquisition_path=[
                    {
                        "step_id": 1,
                        "action": "read_supplement_text",
                        "tool": "supplement_parser",
                        "args": {"supplement_id": supplement_id},
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


def _infer_conditions(text: str, start: int, end: int, entity: str | None) -> tuple[str | None, dict[str, str]]:
    """Extract only explicit, local experimental conditions from result prose.

    This is deliberately conservative: an absent condition is represented as
    ``not_extracted`` in ResultCard rather than guessed from a whole paragraph.
    The raw paragraph remains the evidence of record.
    """
    context = _semantic_text(text[max(0, start - 420):min(len(text), end + 180)])
    fields: dict[str, str] = {}
    normalized_entity = _semantic_text(entity).strip() if entity else None
    if normalized_entity:
        fields["sample_or_entity"] = normalized_entity
    if normalized_entity and re.search(rf"\b{_CELL_LINE_PATTERN}\b", normalized_entity, re.IGNORECASE):
        fields["cell_line"] = normalized_entity
    else:
        match = re.search(rf"\b{_CELL_LINE_PATTERN}\b", context, re.IGNORECASE)
        if match:
            fields["cell_line"] = match.group(0)
    patterns = (
        ("compound_or_treatment", r"(?:treated with|treatment with|concentrations? of|dose of|effect of)\s+(?:the\s+)?([A-Za-z0-9][A-Za-z0-9 -]{1,50}?)(?=\s+(?:at|for|in|on|was|were|and)\b|[,.;]|$)"),
        ("dose_or_concentration", r"(?:at|with|of|dose(?:s)?(?: of)?)\s*(\d+(?:\.\d+)?\s*(?:μM|uM|nM|pM|mM|M|mol/L|mmol/L|μmol/L|umol/L|nmol/L|mg/mL|μg/mL|ug/mL|ng/mL|U/ml|U/mL))"),
        ("exposure_time", r"(?:for|after|at)\s*(\d+(?:\.\d+)?\s*(?:h|min|s|ms|day|d))"),
        ("assay", r"\b((?:CCK-?8|WST-?8|MTT|Annexin V|flow cytometry|Western blot)[^.;,]{0,40})"),
        # Domain-neutral condition vocabulary.  These patterns intentionally
        # require an explicit label so a nearby number is not promoted to a
        # condition merely because it has a scientific unit.
        ("temperature", r"\b(?:temperature|temp(?:erature)?)\s*(?:of|was|were|is|=|:)\s*(\d+(?:\.\d+)?\s*(?:°C|C|K))"),
        ("pressure", r"\bpressure\s*(?:of|was|were|is|=|:)\s*(\d+(?:\.\d+)?\s*(?:Pa|kPa|MPa|bar))"),
        ("method", r"\b(?:measured|quantified|determined|analysed|analyzed|evaluated|assessed)\s+(?:using|by|with)\s+([^.;,]{2,70})"),
        ("method", r"\b(?:method|assay|protocol)\s*(?:used|was|were|is|=|:)\s*([^.;,]{2,70})"),
    )
    for key, pattern in patterns:
        match = re.search(pattern, context, re.IGNORECASE)
        if match:
            value = " ".join(match.group(1).split()).strip(" ,.;")
            # Do not echo the candidate's own value as its condition.  This
            # commonly happens with ``yield of 85 %`` or ``temperature was
            # 37 C``; only a distinct nearby setting should be retained.
            if key in {"dose_or_concentration", "exposure_time", "temperature", "pressure"}:
                target_display = " ".join(_semantic_text(text[start:end]).split()).casefold()
                if " ".join(_semantic_text(value).split()).casefold() == target_display:
                    continue
            if value and key not in fields:
                fields[key] = value
    # Keep generic names alongside the older biomedical aliases so existing
    # domain profiles remain readable while new profiles can consume the
    # domain-neutral vocabulary.
    if "compound_or_treatment" in fields:
        fields.setdefault("treatment_or_input", fields["compound_or_treatment"])
    if "exposure_time" in fields:
        fields.setdefault("exposure_time_or_duration", fields["exposure_time"])
    if "assay" in fields:
        fields.setdefault("assay_or_method", fields["assay"])
    if "method" in fields:
        fields.setdefault("assay_or_method", fields["method"])
    if re.search(r"\bcontrol(?: group| cells)?\b", context, re.IGNORECASE):
        fields["control_group"] = "control"
    uncertainty = re.search(r"\b\d+(?:\.\d+)?\s*±\s*\d+(?:\.\d+)?\s*[%A-Za-zμµ/]+", context)
    if uncertainty:
        fields["replicate_or_error_definition"] = uncertainty.group(0)
    if not fields:
        return None, {}
    return "; ".join(f"{key}={value}" for key, value in fields.items()), fields


def _numeric_question(
    text: str,
    start: int,
    end: int,
    paragraph_id: str,
    unit: str,
) -> tuple[str, str, str | None]:
    semantic = _semantic_text(text)
    prefix = semantic[max(0, start - 600):start]
    suffix = semantic[end:min(len(semantic), end + 140)]
    metric = "numeric result"
    metric_rules = (
        (r"IC\s*50", "IC50"),
        (r"cell viability reduction", "cell viability reduction"),
        (r"viability", "cell viability"),
        (r"response", "response"),
        (r"yield", "yield"),
        (r"accuracy", "accuracy"),
        (r"concentration", "concentration"),
        (r"temperature", "temperature"),
        (r"pressure", "pressure"),
        (r"duration|exposure time", "duration"),
        (r"purity", "purity"),
        (r"efficien(?:cy|t)", "efficiency"),
        (r"intensity", "intensity"),
        (r"diameter", "diameter"),
        (r"width", "width"),
        (r"height", "height"),
        (r"length", "length"),
        (r"area", "area"),
        (r"mass", "mass"),
        (r"volume", "volume"),
        (r"density", "density"),
        (r"energy", "energy"),
        (r"power", "power"),
        (r"frequency", "frequency"),
        (r"wavelength", "wavelength"),
        (r"conductivity", "conductivity"),
        (r"resistance", "resistance"),
        (r"modulus", "modulus"),
        (r"rate", "rate"),
    )
    best_distance: int | None = None
    explicit_metric: tuple[int, str] | None = None
    for pattern, label in metric_rules:
        if label in {"IC50", "cell viability reduction", "cell viability"}:
            for match in re.finditer(pattern, prefix, re.IGNORECASE):
                distance = len(prefix) - match.end()
                if explicit_metric is None or distance < explicit_metric[0]:
                    explicit_metric = (distance, label)
    # Keep semantic cues local.  A distant mention of “IC50” in the same
    # paragraph must not relabel a later dose/time condition as an IC50 result.
    if explicit_metric is not None and explicit_metric[0] <= 220:
        metric = explicit_metric[1]
        best_distance = explicit_metric[0]
    elif explicit_metric is not None:
        explicit_metric = None
    if unit in {"h", "min", "s", "ms", "day", "d"}:
        # A time value is a treatment/exposure condition only when nearby
        # wording makes that role explicit (``for 6 h``, ``incubated for``).
        # Phrases such as ``the measured duration was 2 day`` are themselves
        # generic scientific outcomes and should remain eligible results.
        local_prefix = _local_clause(prefix, limit=320)
        outcome_duration = re.search(
            r"\b(?:duration|period|runtime|latency|observation\s+time|measurement\s+time)"
            r"\s*(?:of|was|were|is|=|:)?\s*$",
            local_prefix,
            re.IGNORECASE,
        )
        condition_duration = re.search(
            r"(?:\bfor|\bafter|\bduring|\bincubat(?:ed|ion)?|\bexpos(?:ed|ure)|\btreated)"
            r"\s*$",
            local_prefix,
            re.IGNORECASE,
        )
        metric = "duration" if outcome_duration and not condition_duration else "treatment duration"
        best_distance = 0
    elif explicit_metric is None and unit in {"μM", "uM", "nM", "pM", "mM", "M", "mol/L", "mmol/L", "μmol/L", "umol/L", "nmol/L", "mg/mL", "μg/mL", "ug/mL", "ng/mL", "U/ml", "U/mL"}:
        # Bound condition cues to the current sentence, but allow a long
        # sentence (for example a concentration series) to retain its lead-in
        # treatment wording.
        local_prefix = _local_clause(prefix)
        condition_concentration = re.search(
            r"(?:\bat|\bwith|\bdose(?:s)?(?:\s+of)?|\btreated|\bcultured|\bincubated|\bstock|\bdilut|"
            r"\b(?:highest|lowest|different)\s+concentration(?:s)?|\bconcentration(?:s)?\s+of)\b.{0,200}$",
            local_prefix,
            re.IGNORECASE,
        )
        reported_concentration = re.search(
            r"\bconcentration(?:s)?\b[^.;]{0,60}\b(?:was|were|is|are|measured|determined|reported|found)\b[^.;]{0,30}$",
            local_prefix,
            re.IGNORECASE,
        )
        strong_condition_concentration = re.search(
            r"\b(?:highest|lowest|different|increasing|decreasing)\s+concentration(?:s)?\b",
            local_prefix,
            re.IGNORECASE,
        )
        if condition_concentration and (not reported_concentration or strong_condition_concentration):
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
    elif re.search(
        r"(?:proportion|proportions|percentage|percentages|percent|rate)\s+of\b"
        r"[^.;]{0,120}\b[SGG0-9/→-]+\s*phase",
        prefix,
        re.IGNORECASE,
    ):
        metric = "cell-cycle proportion"

    entity = None
    # Results are often reported as a value list in one sentence, e.g.
    # ``13 μM in MCF-7 cells and 16 μM in MDA-MB-231 cells``. Bind each
    # value to the nearest explicit cell line after its own span before using
    # broader noun-phrase heuristics. This avoids assigning both values to
    # the first cell line (or leaving both entities unset).
    after_cell_line = re.search(rf"\b(?:in|from|for)\s+({_CELL_LINE_PATTERN})\b", suffix, re.IGNORECASE)
    if after_cell_line:
        entity = after_cell_line.group(1)
    after = re.match(
        r"\s*(?:of\s+(?:the\s+)?control\)?\s*)?(?:was\s+|were\s+)?for\s+([^;,.()]+)",
        suffix,
        re.IGNORECASE,
    )
    if not entity and after:
        entity = " ".join(after.group(1).split()).strip()
    if not entity:
        proportion_entities = list(re.finditer(
            rf"(?:proportions?|percentages?|percent(?:age)?)\s+of\s+(?:the\s+)?(?:[A-Za-z0-9/→-]+\s+phase\s+of\s+)?({_CELL_LINE_PATTERN})\s+cells?",
            prefix,
            re.IGNORECASE,
        ))
        if proportion_entities:
            entity = proportion_entities[-1].group(1)
    if not entity and metric in {"apoptosis proportion", "cell-cycle proportion", "cell viability", "cell viability reduction"}:
        # Some prose inserts the assay/phase between the metric and the cell
        # line (``proportion of the S phase of SW1116 cells``). In that case,
        # bind the nearest domain identifier rather than an earlier treatment
        # name from the same paragraph.
        identifiers = list(re.finditer(rf"\b{_CELL_LINE_PATTERN}\b", prefix, re.IGNORECASE))
        if identifiers:
            entity = identifiers[-1].group(0)
    if not entity:
        concentration_entity = re.search(r"concentrations?\s+of\s+([A-Za-z0-9][A-Za-z0-9 -]{1,50})", prefix, re.IGNORECASE)
        if concentration_entity:
            entity = " ".join(concentration_entity.group(1).split()).strip()
            entity = re.split(r"\s+(?:to|for|and|were|was)\s+", entity, maxsplit=1, flags=re.IGNORECASE)[0]
    if not entity:
        metric_before = re.search(
            r"([^.;]{2,100}?)\s+(?:alone\s+)?(?:had|has|showed|reported)?\s*(?:an?\s+)?"
            r"(?:IC\s*50|viability|response|yield|temperature|pressure|concentration|duration|purity|efficiency|intensity|accuracy|"
            r"diameter|width|height|length|area|mass|volume|density|energy|power|frequency|wavelength|conductivity|resistance|modulus|rate)"
            r"\s+(?:of|was|were|is|are|=)\s*$",
            prefix,
            re.IGNORECASE,
        )
        if metric_before:
            entity = " ".join(metric_before.group(1).split()).strip()
            if "," in entity:
                entity = entity.rsplit(",", 1)[-1].strip()
            # Strip reporting verbs/articles that are not the experimental
            # entity (``Sample A achieved a yield ...`` -> ``Sample A``).
            entity = re.sub(
                r"\s+(?:achieved|reached|reported|showed|had|gave|yielded)\s+(?:an?\s+)?$",
                "",
                entity,
                flags=re.IGNORECASE,
            ).strip()
    if not entity:
        # Common neutral labels provide a stable entity when the sentence
        # uses ``Batch A achieved ...`` or ``Specimen 2 showed ...`` rather
        # than an ``... was reported for ...`` construction.
        labeled_entity = re.search(
            r"\b((?:sample|batch|group|specimen|material|run|trial|condition)"
            r"(?:\s+id)?\s+[A-Za-z0-9][A-Za-z0-9 _-]{0,40}?)"
            r"\s+(?=(?:achieved|reached|reported|showed|had|gave|yielded|"
            r"(?:an?\s+)?(?:yield|temperature|pressure|concentration|duration|purity|efficiency|intensity|accuracy|"
            r"diameter|width|height|length|area|mass|volume|density|energy|power|frequency|wavelength|conductivity|resistance|modulus|rate)\b))",
            prefix,
            re.IGNORECASE,
        )
        if labeled_entity:
            entity = " ".join(labeled_entity.group(1).split()).strip(" ,.;:")
    # If an intervening metric phrase made the broad heuristic capture text
    # such as ``temperature was 37 C and``, prefer the nearest explicit
    # neutral label (``Batch A``/``Sample 2``) from the same clause.
    labeled_context = re.search(
        r"\b((?:sample|batch|group|specimen|material|run|trial|condition)"
        r"(?:\s+id)?\s+[A-Za-z0-9][A-Za-z0-9 _-]{0,40}?)\b",
        _local_clause(prefix),
        re.IGNORECASE,
    )
    if labeled_context and not (entity and re.search(rf"\b{_CELL_LINE_PATTERN}\b", entity, re.IGNORECASE)):
        labeled_value = _clean_entity(labeled_context.group(1))
        if labeled_value:
            entity = labeled_value
    entity = _clean_entity(entity)
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
    "measurement", "characterization", "analysis", "quantitative", "data", "observations",
)
_METHOD_SECTION_TERMS = (
    "method", "methodology", "materials and methods", "reagent", "protocol", "statistical", "production",
    "sample preparation", "experimental section", "fabrication", "synthesis",
)
_RESULT_TEXT_TERMS = (
    "ic50", "viability", "yield", "response", "reduction", "increase", "decrease", "higher", "lower",
    "significant", "efficacy", "fold", "correlated", "accuracy", "error", "performance",
    "measurement", "measured", "temperature", "pressure", "concentration", "duration", "purity",
    "efficiency", "intensity", "absorbance", "conductivity", "resistance", "modulus", "diameter",
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
        metric = answer.get("metric")
        unit = str(answer.get("unit", ""))
        modality = str((candidate.evidence[0] if candidate.evidence else {}).get("modality", ""))
        # A table column is already an explicit result schema (for example a
        # reported temperature or pressure); do not discard it merely because
        # the same unit can denote a prose experimental condition. The
        # condition-only filters below apply to free text/figure evidence.
        if modality != "table" and metric in {"treatment duration", "treatment concentration", "time"}:
            return False
        if modality != "table" and metric in {"duration", "temperature", "pressure", "concentration"}:
            # Generic result prose may explicitly report a measured duration,
            # temperature or pressure.  Drop it only when the local wording
            # marks the value as an experimental setting (``incubated at
            # 37 C``, ``under 2 kPa``), while retaining ``temperature was ...``
            # and analogous outcome statements.
            evidence_text = ""
            if candidate.acquisition_path:
                evidence_text = str(candidate.acquisition_path[0].get("output", ""))
            if not evidence_text and candidate.evidence:
                evidence_text = str(candidate.evidence[0].get("span_text", ""))
            display = str(candidate.answer.get("display", ""))
            display_start = evidence_text.find(display)
            prefix = evidence_text[:display_start] if display_start >= 0 else evidence_text
            condition_tail = re.search(
                r"(?:\bat|\bunder|\bmaintained|\bincubated|\bexposed|\btreated|\bfor|\bafter|\bduring|"
                r"\bset\s+to|\broom|\bambient|\bpressure\s+of|\btemperature\s+of)\s*$",
                prefix[-180:],
                re.IGNORECASE,
            )
            explicit_outcome = re.search(
                r"\b(?:duration|period|runtime|latency|temperature|pressure|concentration)\s*(?:of|was|were|is|=|:)\s*$",
                prefix[-180:],
                re.IGNORECASE,
            )
            strong_condition = re.search(
                r"\b(?:highest|lowest|different|increasing|decreasing)\s+concentration(?:s)?\b",
                prefix[-180:],
                re.IGNORECASE,
            )
            if strong_condition or (condition_tail and not explicit_outcome):
                return False
        if modality != "table" and metric == "intensity" and unit in {
            "μM", "uM", "nM", "pM", "mM", "M", "mol/L", "mmol/L", "μmol/L", "umol/L", "nmol/L",
        }:
            # Fluorescence/ROS prose can mention a concentration series next
            # to an intensity noun; those molar values are dose settings, not
            # measured intensity results.
            evidence_text = ""
            if candidate.acquisition_path:
                evidence_text = str(candidate.acquisition_path[0].get("output", ""))
            prefix = evidence_text[:evidence_text.find(str(candidate.answer.get("display", "")))]
            clause = _local_clause(prefix)
            if re.search(r"\b(?:treated|treatment|different|indicated|concentration|dose|control\s+group|μM|uM)\b", clause, re.IGNORECASE):
                return False
        if modality != "table" and metric == "numeric result":
            return False
        if modality != "table" and metric == "IC50" and unit in {"μM", "uM", "nM", "pM", "mM", "M", "mol/L", "mmol/L", "μmol/L", "umol/L", "nmol/L", "mg/mL", "μg/mL", "ug/mL", "ng/mL", "U/ml", "U/mL"}:
            # A value introduced by “at 5 μM” or “concentration ... was
            # 10 μM” is a dose condition even when an earlier sentence says
            # “IC50”.  True IC50 results are introduced by “was/were” in the
            # result clause or table.
            evidence_text = ""
            if candidate.acquisition_path:
                evidence_text = str(candidate.acquisition_path[0].get("output", ""))
            if not evidence_text and candidate.evidence:
                evidence_text = str(candidate.evidence[0].get("span_text", ""))
            display = str(candidate.answer.get("display", ""))
            display_start = evidence_text.find(display)
            if display_start >= 0 and re.search(r"(?:\bat|concentration(?:s)?\s+of|concentration\s+[^.;]{0,40}\s+was)\s*$", evidence_text[:display_start], re.IGNORECASE):
                return False
        # In result prose, concentrations and durations often sit next to a
        # true outcome (e.g. apoptosis or cell-cycle percentages).  A numeric
        # candidate whose semantic metric is an outcome but whose unit is a
        # concentration/time unit is the experimental condition, not a result.
        if metric in {"apoptosis proportion", "cell-cycle proportion", "cell viability", "cell viability reduction"} and unit in {
            "h", "min", "s", "ms", "μM", "uM", "nM", "pM", "mM", "M", "mg/mL", "μg/mL", "ug/mL", "ng/mL", "U/ml", "U/mL",
        }:
            return False
    return True
