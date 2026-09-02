"""Gold 数据卡的最小字段。第一周冻结前可以改，改完后不要 silently 加必填项。"""

from __future__ import annotations

from typing import Any, Literal, TypedDict


QualityTier = Literal["raw", "silver", "gold"]
TaskKind = Literal["qa", "lookup", "arith", "relation"]


class EvidenceSpan(TypedDict):
    doi: str
    page: int
    table_id: str | None
    row: int | None
    col: int | None
    quote: str


class PathStep(TypedDict):
    tool: str
    args: dict[str, Any]
    output: str | None


class ResultCard(TypedDict):
    id: str
    question: str
    answer: str
    unit: str | None
    conditions: list[str]
    task_kind: TaskKind
    evidence: list[EvidenceSpan]
    path: list[PathStep]
    verified: bool
    verifier_value: str | None
    tolerance: str | None
    license: str
    quality: QualityTier
    notes: list[str]


WHITELIST_TOOLS = (
    "read_text_span",
    "extract_table_cell",
    "parse_number_unit",
    "unit_convert",
    "arith_eval",
    "sympy_eval",
    "lookup_condition",
)
