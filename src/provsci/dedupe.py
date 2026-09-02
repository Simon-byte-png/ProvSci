"""Deterministic result-level duplicate grouping for audit and curation."""

from __future__ import annotations

import hashlib
from collections import defaultdict
from typing import Any


def annotate_duplicate_groups(samples: list[dict[str, Any]]) -> dict[str, int]:
    """Attach stable duplicate-group IDs without silently dropping evidence.

    A repeated value from a table and a result paragraph is useful when both
    sources agree.  We retain both samples, mark them as
    ``cross_evidence_consistent`` and expose group counts for downstream
    deduplication.  Conflicting values do not share a duplicate group because
    their normalized value is part of the key.  We only call two values a
    conflict when they come from different evidence contexts (table/row,
    paragraph, figure, or supplement).  Multiple values in one paragraph or
    table row commonly represent a dose/time series or separate summary
    columns; the v0 parser cannot safely bind those values to conditions, so
    treating them as contradictory would create false human-review alarms.
    """
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    conflict_groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for sample in samples:
        card = sample.get("result_card", {})
        answer = sample.get("task", {}).get("answer", {})
        if sample.get("task", {}).get("type") == "relation":
            key = (
                sample.get("source", {}).get("doc_id"),
                "relation",
                str(answer.get("value", "")).casefold(),
                str(answer.get("subject", "")).casefold(),
                str(answer.get("object", "")).casefold(),
            )
        else:
            key = (
                sample.get("source", {}).get("doc_id"),
                str(card.get("metric", answer.get("metric", ""))).casefold(),
                str(card.get("entity", answer.get("entity", ""))).casefold(),
                str(card.get("value", answer.get("value", ""))),
                str(card.get("unit", answer.get("unit", ""))).casefold(),
            )
        group_key = hashlib.sha1("|".join(map(str, key)).encode("utf-8")).hexdigest()[:12]
        groups[group_key].append(sample)
        condition = card.get("condition", {}) or {}
        conflict_key = (
            sample.get("source", {}).get("doc_id"),
            str(card.get("metric", answer.get("metric", ""))).casefold(),
            str(card.get("entity", answer.get("entity", ""))).casefold(),
            str(card.get("unit", answer.get("unit", ""))).casefold(),
            str(condition.get("text", "")).casefold(),
        )
        conflict_id = hashlib.sha1("|".join(map(str, conflict_key)).encode("utf-8")).hexdigest()[:12]
        conflict_groups[conflict_id].append(sample)
    duplicate_count = 0
    for group_key, rows in groups.items():
        status = "cross_evidence_consistent" if len(rows) > 1 else "single"
        for sample in rows:
            sample.setdefault("result_card", {})["duplicate_group_id"] = f"dup-{group_key}"
            sample["result_card"]["duplicate_status"] = status
        if len(rows) > 1:
            duplicate_count += len(rows)
    conflict_count = 0
    for rows in conflict_groups.values():
        values = {
            str((row.get("result_card", {}) or {}).get("value", row.get("task", {}).get("answer", {}).get("value", "")))
            for row in rows
        }
        evidence_contexts = {_evidence_context_key(row) for row in rows}
        if len(values) <= 1 or len(evidence_contexts) <= 1:
            continue
        conflict_count += len(rows)
        first = rows[0]
        first_card = first.get("result_card", {}) or {}
        first_answer = first.get("task", {}).get("answer", {})
        condition = first_card.get("condition", {}) or {}
        conflict_group_id = hashlib.sha1("|".join(map(str, (
            first.get("source", {}).get("doc_id"),
            first_card.get("metric", first_answer.get("metric", "")),
            first_card.get("entity", first_answer.get("entity", "")),
            first_card.get("unit", first_answer.get("unit", "")),
            condition.get("text", ""),
        ))).encode("utf-8")).hexdigest()[:12]
        for sample in rows:
            card = sample.setdefault("result_card", {})
            card["duplicate_status"] = "conflict"
            card["conflict_group_id"] = f"conflict-{conflict_group_id}"
            quality = sample.setdefault("quality", {})
            quality["needs_human_review"] = True
            quality["failure_mode"] = "conflicting_values"
    return {
        "duplicate_groups": sum(len(rows) > 1 for rows in groups.values()),
        "duplicate_claims": duplicate_count,
        "conflict_groups": sum(
            len(rows) > 1
            and len({str((row.get("result_card", {}) or {}).get("value", row.get("task", {}).get("answer", {}).get("value", ""))) for row in rows}) > 1
            and len({_evidence_context_key(row) for row in rows}) > 1
            for rows in conflict_groups.values()
        ),
        "conflict_claims": conflict_count,
    }


def _evidence_context_key(sample: dict[str, Any]) -> tuple[str, str, str]:
    """Return the coarsest evidence context that can support a conflict.

    Character spans and table columns are intentionally excluded.  A single
    paragraph may contain a whole dose/time series, and a single table row may
    have mean/error or condition columns.  Those are not independently
    comparable claims until a domain adapter binds the relevant condition.
    """
    evidence = sample.get("evidence") or [{}]
    item = evidence[0] if isinstance(evidence[0], dict) else {}
    modality = str(item.get("modality", "unknown"))
    locator = item.get("locator") or {}
    if modality == "table":
        context = locator.get("table_id", "")
        row = locator.get("row_index", locator.get("row", ""))
        return modality, str(context), str(row)
    if modality == "text":
        return modality, str(locator.get("paragraph_id", "")), ""
    if modality == "supplement":
        return modality, str(locator.get("supplement_id", "")), ""
    if modality == "figure":
        return modality, str(locator.get("figure_id", "")), ""
    return modality, str(locator), ""
