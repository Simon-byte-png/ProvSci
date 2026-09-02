"""Small JSON-native models shared by the v0 pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .profile import DEFAULT_DOMAIN


class InputError(ValueError):
    """Raised when a document package or generated sample is malformed."""


@dataclass(frozen=True)
class DocumentPackage:
    doc_id: str
    title: str
    year: int
    license: str
    local_path: str
    paragraphs: list[dict[str, Any]] = field(default_factory=list)
    tables: list[dict[str, Any]] = field(default_factory=list)
    figures: list[dict[str, Any]] = field(default_factory=list)
    supplements: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "DocumentPackage":
        required = ("doc_id", "title", "year", "license", "local_path")
        missing = [key for key in required if key not in raw or raw[key] in (None, "")]
        if missing:
            raise InputError(f"document missing required fields: {', '.join(missing)}")
        return cls(
            doc_id=str(raw["doc_id"]),
            title=str(raw["title"]),
            year=int(raw["year"]),
            license=str(raw["license"]),
            local_path=str(raw["local_path"]),
            paragraphs=list(raw.get("paragraphs", [])),
            tables=list(raw.get("tables", [])),
            figures=list(raw.get("figures", [])),
            supplements=list(raw.get("supplements", [])),
            metadata=dict(raw.get("metadata", {})),
        )

    def table(self, table_id: str) -> dict[str, Any]:
        for table in self.tables:
            if str(table.get("id")) == table_id:
                return table
        raise InputError(f"table not found: {table_id}")

    def paragraph(self, paragraph_id: str) -> dict[str, Any]:
        for paragraph in self.paragraphs:
            if str(paragraph.get("id")) == paragraph_id:
                return paragraph
        raise InputError(f"paragraph not found: {paragraph_id}")

    def figure(self, figure_id: str) -> dict[str, Any]:
        for figure in self.figures:
            if str(figure.get("id")) == figure_id:
                return figure
        raise InputError(f"figure not found: {figure_id}")

    def supplement(self, supplement_id: str) -> dict[str, Any]:
        for supplement in self.supplements:
            if str(supplement.get("id")) == supplement_id:
                return supplement
        raise InputError(f"supplement not found: {supplement_id}")


@dataclass(frozen=True)
class Candidate:
    candidate_id: str
    doc_id: str
    subject: str
    task_type: str
    question: str
    answer: dict[str, Any]
    evidence: list[dict[str, Any]]
    acquisition_path: list[dict[str, Any]]
    page_span: list[int]

    def to_sample(self, license_name: str, title: str, local_path: str) -> dict[str, Any]:
        answer = dict(self.answer)
        task_type = self.task_type
        if task_type == "numeric_qa":
            result_type = "measurement"
        elif task_type == "relation":
            result_type = "comparison_relation"
        else:
            result_type = "scientific_claim"
        condition_text = answer.get("condition")
        evidence_modality = str((self.evidence[0] if self.evidence else {}).get("modality", ""))
        condition_source = answer.get("condition_source") or (
            "column_header" if evidence_modality == "table" and condition_text
            else "local_text" if condition_text
            else "not_extracted"
        )
        result_card = {
            "schema_version": "result_card.v1",
            "domain": DEFAULT_DOMAIN,
            "result_type": result_type,
            "entity": answer.get("entity") or answer.get("subject") or self.subject,
            "metric": answer.get("metric") or ("relation" if task_type == "relation" else None),
            "value": answer.get("value"),
            "unit": str(answer.get("unit", "")),
            "display": answer.get("display", str(answer.get("value", ""))),
            "condition": {
                "text": condition_text,
                "source": condition_source,
                "status": "explicit" if condition_text else "not_extracted",
                "fields": dict(answer.get("condition_fields") or {}),
            },
            "uncertainty": answer.get("uncertainty"),
            "raw_value": answer.get("display", str(answer.get("value", ""))),
            "normalized_value": {
                "value": answer.get("value"),
                "unit": str(answer.get("unit", "")),
            },
        }
        if task_type == "relation":
            result_card["subject"] = answer.get("subject")
            result_card["object"] = answer.get("object")
        return {
            "id": self.candidate_id,
            "source": {
                "doc_id": self.doc_id,
                "title": title,
                "year": 0,
                "license": license_name,
                "local_path": local_path,
                "page_span": self.page_span,
            },
            "task": {
                "type": self.task_type,
                "subject": self.subject,
                "question": self.question,
                "answer": answer,
            },
            "result_card": result_card,
            "evidence": self.evidence,
            "acquisition_path": self.acquisition_path,
            "verification": {
                "status": "unknown",
                "recomputed": None,
                "tolerance": {"rel": 0.02, "abs": None},
                "verifier_version": "provverify_v0.1",
                "checked_at": None,
                "evidence_checked": False,
            },
            "quality": {
                "needs_human_review": False,
                "failure_mode": None,
                "annotator": "agent_v0",
                "prompt_ver": "harvest_v0.1",
            },
            "split": "train",
        }
