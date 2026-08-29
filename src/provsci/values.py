"""Parsing and conversion helpers for scientific values."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass


class ValueParseError(ValueError):
    """Raised when a scientific number/unit value cannot be parsed."""


@dataclass(frozen=True)
class NumberUnit:
    value: float
    unit: str

    def as_dict(self) -> dict[str, float | str]:
        return {"value": self.value, "unit": self.unit}


# The initial registry is intentionally small and explicit. New dimensions
# should be added with tests instead of silently accepting unknown units.
_UNIT_FACTORS: dict[str, tuple[str, float, str]] = {
    "M": ("concentration", 1.0, "M"),
    "mM": ("concentration", 1e-3, "M"),
    "uM": ("concentration", 1e-6, "M"),
    "um": ("concentration", 1e-6, "M"),
    "μM": ("concentration", 1e-6, "M"),
    "nM": ("concentration", 1e-9, "M"),
    "nm": ("concentration", 1e-9, "M"),
    "pM": ("concentration", 1e-12, "M"),
    "%": ("ratio", 1.0, "%"),
    "K": ("temperature", 1.0, "K"),
    "C": ("temperature", 1.0, "C"),
    "°C": ("temperature", 1.0, "C"),
    "s": ("time", 1.0, "s"),
    "ms": ("time", 1e-3, "s"),
    "min": ("time", 60.0, "s"),
    "h": ("time", 3600.0, "s"),
    "mg": ("mass", 1e-3, "g"),
    "g": ("mass", 1.0, "g"),
    "kg": ("mass", 1e3, "g"),
    "mL": ("volume", 1.0, "mL"),
    "L": ("volume", 1000.0, "mL"),
    "uL": ("volume", 1e-3, "mL"),
    "μL": ("volume", 1e-3, "mL"),
    "U/ml": ("activity_concentration", 1.0, "U/ml"),
    "U/mL": ("activity_concentration", 1.0, "U/ml"),
    "mg/mL": ("mass_concentration", 1.0, "mg/mL"),
    "ug/mL": ("mass_concentration", 1e-3, "mg/mL"),
    "μg/mL": ("mass_concentration", 1e-3, "mg/mL"),
    "ng/mL": ("mass_concentration", 1e-6, "mg/mL"),
}

_NUMBER_RE = r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?"
_VALUE_RE = re.compile(rf"^\s*({_NUMBER_RE})\s*([^\d\s].*?)?\s*$")
_TEXT_VALUE_RE = re.compile(rf"(?<![\w.])({_NUMBER_RE})\s*(%|°?[A-Za-zμµ]+)(?!\w)")
_TEXT_MEASUREMENT_RE = re.compile(
    rf"(?<![\w.])({_NUMBER_RE})(?:\s*[±+]\s*({_NUMBER_RE}))?(\s*)(%|°?[A-Za-zμµ]+(?:/[A-Za-zμµ]+)?)(?!\w)"
)
_VALUE_ONLY_MEASUREMENT_RE = re.compile(
    rf"^\s*({_NUMBER_RE})(?:\s*[±+]\s*({_NUMBER_RE}))?\s*$"
)


def parse_number_unit(value: object) -> NumberUnit:
    if isinstance(value, bool):
        raise ValueParseError("boolean is not a scientific number")
    if isinstance(value, (int, float)):
        if not math.isfinite(float(value)):
            raise ValueParseError("number must be finite")
        return NumberUnit(float(value), "")
    if not isinstance(value, str):
        raise ValueParseError(f"unsupported value type: {type(value).__name__}")

    match = _VALUE_RE.match(value.replace("µ", "μ"))
    if not match:
        raise ValueParseError(f"could not parse number/unit: {value!r}")
    number = float(match.group(1))
    unit = (match.group(2) or "").strip()
    if unit and unit not in _UNIT_FACTORS:
        raise ValueParseError(f"unknown unit: {unit}")
    return NumberUnit(number, unit)


def extract_number_unit_occurrences(text: str) -> list[tuple[int, int, NumberUnit]]:
    """Return unit-bearing numeric spans in document text, in source order."""
    occurrences: list[tuple[int, int, NumberUnit]] = []
    for match in _TEXT_VALUE_RE.finditer(text.replace("µ", "μ")):
        raw = f"{match.group(1)} {match.group(2)}"
        try:
            parsed = parse_number_unit(raw)
        except ValueParseError:
            continue
        occurrences.append((match.start(), match.end(), parsed))
    return occurrences


def extract_measurement_occurrences(text: str) -> list[tuple[int, int, NumberUnit, float | None]]:
    """Return value, optional uncertainty, unit and source span for measurements."""
    occurrences: list[tuple[int, int, NumberUnit, float | None]] = []
    for match in _TEXT_MEASUREMENT_RE.finditer(text.replace("µ", "μ")):
        unit = match.group(4)
        if unit in {"C", "K", "g", "M"} and not match.group(3) and not text[match.start():match.end()].startswith("°"):
            continue
        raw = f"{match.group(1)} {unit}"
        try:
            parsed = parse_number_unit(raw)
        except ValueParseError:
            continue
        uncertainty = float(match.group(2)) if match.group(2) is not None else None
        occurrences.append((match.start(), match.end(), parsed, uncertainty))
    return occurrences


def parse_measurement(value: object, default_unit: str = "") -> dict[str, object]:
    """Parse a value with optional uncertainty and an optional header unit."""
    if isinstance(value, str):
        occurrences = extract_measurement_occurrences(value)
        if occurrences:
            _, _, parsed, uncertainty = occurrences[0]
            return {"value": parsed.value, "unit": parsed.unit, "uncertainty": uncertainty}
        match = _VALUE_ONLY_MEASUREMENT_RE.match(value)
        if match and default_unit:
            parsed = parse_number_unit(f"{match.group(1)} {default_unit}")
            uncertainty = float(match.group(2)) if match.group(2) is not None else None
            return {"value": parsed.value, "unit": parsed.unit, "uncertainty": uncertainty}
    parsed = parse_number_unit(value)
    return {"value": parsed.value, "unit": parsed.unit, "uncertainty": None}


def convert(value: NumberUnit, target_unit: str) -> NumberUnit:
    if not value.unit:
        raise ValueParseError("cannot convert a unitless value")
    if target_unit not in _UNIT_FACTORS:
        raise ValueParseError(f"unknown target unit: {target_unit}")
    source_dimension, source_factor, source_base = _UNIT_FACTORS[value.unit]
    target_dimension, target_factor, target_base = _UNIT_FACTORS[target_unit]
    if source_dimension != target_dimension:
        raise ValueParseError(f"incompatible units: {value.unit} -> {target_unit}")
    if source_dimension == "temperature" and {value.unit, target_unit} == {"C", "K"}:
        if value.unit == "C" and target_unit == "K":
            return NumberUnit(value.value + 273.15, "K")
        return NumberUnit(value.value - 273.15, "C")
    base_value = value.value * source_factor
    return NumberUnit(base_value / target_factor, target_base)
