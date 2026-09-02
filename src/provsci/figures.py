"""Helpers for replayable structured figure/curve data.

The first figure baseline is intentionally explicit rather than an image
reader: adapters may attach ``axes`` and ``series``/``points`` to a figure
record, after which ProvSci can mine point-level claims without guessing from
pixels.  OCR/VLM extraction can emit the same shape later and remains outside
the dependency-free core.
"""

from __future__ import annotations

import math
from typing import Any, Iterator


def figure_axis(figure: dict[str, Any], axis: str) -> dict[str, Any]:
    """Return normalized metadata for the x/y axis of a figure."""
    axes = figure.get("axes")
    config: Any = axes.get(axis, {}) if isinstance(axes, dict) else {}
    if not isinstance(config, dict):
        config = {"unit": config}
    fallback_unit = figure.get(f"{axis}_unit") or figure.get(f"{axis}Unit") or ""
    fallback_label = figure.get(f"{axis}_label") or figure.get(f"{axis}Label") or axis
    return {
        "label": str(config.get("label") or config.get("name") or fallback_label or axis),
        "unit": str(config.get("unit") or fallback_unit or ""),
    }


def iter_figure_points(figure: dict[str, Any]) -> Iterator[dict[str, Any]]:
    """Yield normalized points from common adapter-exported figure shapes.

    Supported forms are deliberately small and documented by the normalized
    output: ``figure.points``, ``figure.series[*].points`` and
    ``figure.data`` (either a point list or series list).  A point can be a
    mapping with x/y fields or a two-item ``[x, y]`` sequence.
    """
    source: Any = figure.get("series")
    if source is None:
        source = figure.get("data")
    if source is None and figure.get("points") is not None:
        source = [{"name": figure.get("label") or figure.get("id") or "series_1", "points": figure.get("points")}]
    if isinstance(source, dict):
        source = [source]
    if not isinstance(source, list) or not source:
        return
    # A top-level list of point mappings/tuples is a single unnamed series.
    if source and _looks_like_point(source[0]):
        source = [{"name": figure.get("label") or figure.get("id") or "series_1", "points": source}]
    for series_index, raw_series in enumerate(source):
        if isinstance(raw_series, dict):
            series_name = str(raw_series.get("name") or raw_series.get("label") or raw_series.get("id") or f"series_{series_index + 1}")
            points = raw_series.get("points")
            if points is None:
                points = raw_series.get("data")
        elif isinstance(raw_series, list):
            series_name = f"series_{series_index + 1}"
            points = raw_series
        else:
            continue
        if not isinstance(points, list):
            continue
        for point_index, raw_point in enumerate(points):
            normalized = _normalize_point(raw_point)
            if normalized is None:
                continue
            normalized.update({
                "series_index": series_index,
                "series_name": series_name,
                "point_index": point_index,
            })
            yield normalized


def resolve_figure_point(
    figure: dict[str, Any],
    *,
    series_index: int,
    point_index: int,
) -> dict[str, Any]:
    """Resolve one point by stable series/point indexes."""
    for point in iter_figure_points(figure):
        if point["series_index"] == int(series_index) and point["point_index"] == int(point_index):
            return point
    raise KeyError(f"figure point not found: series={series_index}, point={point_index}")


def point_value_for_path(point: dict[str, Any], y_axis: dict[str, Any]) -> Any:
    """Return a path-friendly y value, applying an explicit axis unit."""
    value = point.get("y")
    if isinstance(value, dict):
        return dict(value)
    unit = str(y_axis.get("unit", ""))
    if unit and isinstance(value, (int, float)) and not isinstance(value, bool):
        return f"{_format_number(value)} {unit}"
    return value


def point_display(point: dict[str, Any], y_axis: dict[str, Any]) -> str:
    """Format a point's y value for evidence and human review."""
    value = point.get("y")
    if isinstance(value, dict):
        raw_value = value.get("display", value.get("value", ""))
        unit = str(value.get("unit") or y_axis.get("unit", ""))
        if unit and str(raw_value).strip() and unit not in str(raw_value):
            return f"{raw_value} {unit}"
        return str(raw_value).strip()
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        rendered = _format_number(value)
    else:
        rendered = str(value or "").strip()
    unit = str(y_axis.get("unit", ""))
    if unit and rendered and not _has_explicit_unit(rendered):
        rendered = f"{rendered} {unit}"
    return rendered


def point_x_display(point: dict[str, Any], x_axis: dict[str, Any]) -> str:
    """Format a point's x value with the axis unit for a condition field."""
    value = point.get("x")
    if isinstance(value, dict):
        raw_value = value.get("display", value.get("value", ""))
        unit = str(value.get("unit") or x_axis.get("unit", ""))
        if unit and str(raw_value).strip() and unit not in str(raw_value):
            return f"{raw_value} {unit}"
        return str(raw_value).strip()
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        rendered = _format_number(value)
    else:
        rendered = str(value or "").strip()
    unit = str(x_axis.get("unit", ""))
    if unit and rendered and not _has_explicit_unit(rendered):
        rendered = f"{rendered} {unit}"
    return rendered


def _normalize_point(raw_point: Any) -> dict[str, Any] | None:
    if isinstance(raw_point, dict):
        if "x" not in raw_point and "x_value" in raw_point:
            x = raw_point.get("x_value")
        else:
            x = raw_point.get("x")
        if "y" in raw_point:
            y = raw_point.get("y")
        elif "y_value" in raw_point:
            y = raw_point.get("y_value")
        else:
            y = raw_point.get("value")
        if x is None or y is None:
            return None
        return {"x": x, "y": y, "raw": dict(raw_point)}
    if isinstance(raw_point, (list, tuple)) and len(raw_point) >= 2:
        return {"x": raw_point[0], "y": raw_point[1], "raw": list(raw_point)}
    return None


def _looks_like_point(value: Any) -> bool:
    if isinstance(value, (list, tuple)):
        return len(value) >= 2 and not isinstance(value[0], (dict, list, tuple))
    return isinstance(value, dict) and any(key in value for key in ("x", "x_value")) and any(key in value for key in ("y", "y_value", "value"))


def _format_number(value: int | float) -> str:
    number = float(value)
    if not math.isfinite(number):
        return str(value)
    return f"{number:g}"


def _has_explicit_unit(value: str) -> bool:
    # Axis units in normalized figure data are supplied separately.  This
    # conservative check only avoids appending a second token to values that
    # already end in a conventional scientific unit.
    return bool(value.rsplit(" ", 1)[-1] and any(char.isalpha() or char in "%°μµ" for char in value.rsplit(" ", 1)[-1]))
