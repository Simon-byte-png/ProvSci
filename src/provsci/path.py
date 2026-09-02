"""Deterministic execution of the acquisition-path allowlist."""

from __future__ import annotations

import ast
import math
import operator
import re
from typing import Any

from .models import DocumentPackage, InputError
from .values import NumberUnit, convert, extract_measurement_occurrences, extract_number_unit_occurrences, parse_measurement, parse_number_unit
from .figures import figure_axis, point_value_for_path, resolve_figure_point


class PathExecutionError(ValueError):
    """Raised when a path is invalid or invokes a disallowed operation."""


ALLOWED_ACTIONS = frozenset(
    {
        "extract_table_cell",
        "extract_figure_point",
        "read_text_span",
        "read_figure_alt_text",
        "read_supplement_text",
        "parse_number_unit",
        "parse_measurement",
        "extract_number_unit",
        "unit_convert",
        "arith_eval",
        "extract_relation",
    }
)


def _safe_arithmetic(expression: str) -> float:
    """Evaluate numeric arithmetic without exposing Python names or calls."""
    if len(expression) > 256:
        raise PathExecutionError("expression is too long")
    tree = ast.parse(expression, mode="eval")
    binary_ops = {
        ast.Add: operator.add,
        ast.Sub: operator.sub,
        ast.Mult: operator.mul,
        ast.Div: operator.truediv,
        ast.Pow: operator.pow,
    }
    unary_ops = {ast.UAdd: operator.pos, ast.USub: operator.neg}

    def visit(node: ast.AST) -> float:
        if isinstance(node, ast.Expression):
            return visit(node.body)
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
            return float(node.value)
        if isinstance(node, ast.BinOp) and type(node.op) in binary_ops:
            left, right = visit(node.left), visit(node.right)
            if isinstance(node.op, ast.Pow) and abs(right) > 20:
                raise PathExecutionError("exponent is too large")
            result = binary_ops[type(node.op)](left, right)
            if not isinstance(result, (int, float)) or not math.isfinite(float(result)):
                raise PathExecutionError("arithmetic produced an invalid number")
            return float(result)
        if isinstance(node, ast.UnaryOp) and type(node.op) in unary_ops:
            return float(unary_ops[type(node.op)](visit(node.operand)))
        raise PathExecutionError("expression contains a disallowed operation")

    try:
        return visit(tree)
    except (SyntaxError, ZeroDivisionError, OverflowError) as exc:
        raise PathExecutionError(f"invalid arithmetic expression: {expression!r}") from exc


class PathExecutor:
    def __init__(self, document: DocumentPackage):
        self.document = document

    def execute(self, path: list[dict[str, Any]]) -> tuple[Any, list[dict[str, Any]]]:
        if not path:
            raise PathExecutionError("acquisition path cannot be empty")
        outputs: dict[int, Any] = {}
        trace: list[dict[str, Any]] = []
        for raw_step in path:
            step_id = int(raw_step.get("step_id", 0))
            action = raw_step.get("action")
            if step_id <= 0 or not action:
                raise PathExecutionError("each path step needs a positive step_id and action")
            if step_id in outputs:
                raise PathExecutionError(f"step_id is duplicated: {step_id}")
            if action not in ALLOWED_ACTIONS:
                raise PathExecutionError(f"action is not allowlisted: {action}")
            dependencies = [int(item) for item in raw_step.get("depends_on", [])]
            if any(item not in outputs for item in dependencies):
                raise PathExecutionError(f"step {step_id} has an unresolved dependency")
            args = dict(raw_step.get("args", {}))
            try:
                output = self._run(action, args, outputs, dependencies)
            except (InputError, ValueError, KeyError, TypeError) as exc:
                raise PathExecutionError(f"step {step_id} failed: {exc}") from exc
            outputs[step_id] = output
            trace.append({
                "step_id": step_id,
                "action": action,
                "args": args,
                "depends_on": dependencies,
                "output": _json_value(output),
            })
        return outputs[step_id], trace

    def _run(
        self,
        action: str,
        args: dict[str, Any],
        outputs: dict[int, Any],
        dependencies: list[int],
    ) -> Any:
        def dependency_output(step_key: object) -> Any:
            step_id = int(step_key)
            if step_id not in dependencies:
                raise PathExecutionError(f"step {step_id} is referenced but not declared as a dependency")
            return outputs[step_id]

        if action == "extract_table_cell":
            table = self.document.table(str(args["table_id"]))
            if "page" in args and int(args["page"]) != int(table.get("page", args["page"])):
                raise InputError("table page does not match the document package")
            row_key = str(args["row_key"])
            col = str(args["col"])
            rows = table.get("rows", [])
            if "row_index" in args:
                row_index = int(args["row_index"])
                if row_index < 0 or row_index >= len(rows):
                    raise InputError(f"row index out of range: {row_index}")
                row = rows[row_index]
                if col not in row:
                    raise InputError(f"column not found: {col}")
                return row[col]
            for row in rows:
                label = next(
                    (row.get(key) for key in (
                        "Sample", "sample", "Sample ID", "sample_id", "Cell line", "cell line", "cell_line",
                        "Compound", "compound", "Batch", "batch", "Group", "group", "Specimen", "specimen",
                        "Material", "material", "Treatment", "treatment", "Condition", "condition",
                        "Name", "name", "id",
                    ) if row.get(key) not in (None, "")),
                    None,
                )
                if str(label) == row_key:
                    if col not in row:
                        raise InputError(f"column not found: {col}")
                    return row[col]
            raise InputError(f"row not found: {row_key}")
        if action == "read_text_span":
            paragraph = self.document.paragraph(str(args["paragraph_id"]))
            if "page" in args and int(args["page"]) != int(paragraph.get("page", args["page"])):
                raise InputError("paragraph page does not match the document package")
            return paragraph["text"]
        if action == "read_figure_alt_text":
            figure = self.document.figure(str(args["figure_id"]))
            return str(figure.get("alt_text", ""))
        if action == "extract_figure_point":
            figure = self.document.figure(str(args["figure_id"]))
            point = resolve_figure_point(
                figure,
                series_index=int(args.get("series_index", 0)),
                point_index=int(args["point_index"]),
            )
            axis = str(args.get("value_axis", "y")).casefold()
            if axis not in {"x", "y"}:
                raise InputError("figure value_axis must be x or y")
            return point_value_for_path(point, figure_axis(figure, axis))
        if action == "read_supplement_text":
            supplement = self.document.supplement(str(args["supplement_id"]))
            return str(supplement.get("text", ""))
        if action == "parse_number_unit":
            source = args.get("value")
            if "value_from" in args:
                source = dependency_output(args["value_from"])
            return parse_number_unit(source).as_dict()
        if action == "parse_measurement":
            source = args.get("value")
            if "value_from" in args:
                source = dependency_output(args["value_from"])
            if isinstance(source, dict) and "value" in source:
                return source
            return parse_measurement(source, str(args.get("default_unit", "")))
        if action == "extract_number_unit":
            source = args.get("text")
            if "text_from" in args:
                source = dependency_output(args["text_from"])
            if not isinstance(source, str):
                raise InputError("number extraction requires text")
            occurrences = extract_measurement_occurrences(source)
            index = int(args.get("match_index", 0))
            if index < 0 or index >= len(occurrences):
                raise InputError(f"numeric match index out of range: {index}")
            start, end, parsed, uncertainty = occurrences[index]
            return {
                "value": parsed.value,
                "unit": parsed.unit,
                "span_text": source[start:end],
                "char_span": [start, end],
                "uncertainty": uncertainty,
            }
        if action == "unit_convert":
            source = args.get("value")
            if "value_from" in args:
                source = dependency_output(args["value_from"])
            if isinstance(source, dict):
                parsed = NumberUnit(float(source["value"]), str(source["unit"]))
            else:
                parsed = parse_number_unit(source)
            return convert(parsed, str(args["to"])).as_dict()
        if action == "arith_eval":
            expression = str(args.get("expression", ""))
            for step_id in dependencies:
                output = outputs[step_id]
                if isinstance(output, (int, float)):
                    expression = expression.replace(f"${step_id}", str(output))
                elif isinstance(output, dict) and "value" in output:
                    expression = expression.replace(f"${step_id}", str(output["value"]))
            return {"value": _safe_arithmetic(expression), "unit": str(args.get("unit", ""))}
        if action == "extract_relation":
            source = args.get("text")
            if "text_from" in args:
                source = dependency_output(args["text_from"])
            if not isinstance(source, str):
                raise InputError("relation extraction requires text")
            return _extract_relation(
                source,
                args.get("relation"),
                args.get("subject"),
                args.get("object"),
            )
        raise PathExecutionError(f"unsupported action: {action}")


def _json_value(value: Any) -> Any:
    if isinstance(value, NumberUnit):
        return value.as_dict()
    return value


def extract_relation_claim(text: str) -> dict[str, str]:
    """Parse one allowlisted relation into a stable subject/predicate/object triple."""
    relation_pattern = re.compile(
        r"(?P<subject>[^.;:()]+?)\s+(?:was|were|is|are|showed|shows|had|has|yielded|demonstrated|indicates?)?\s*"
        r"(?:significantly\s+)?(?P<relation>increased|decreased|higher|lower|improved|reduced|positively correlated|negatively correlated)\s+"
        r"(?P<object>[^.;:()]+)",
        re.IGNORECASE,
    )
    match = relation_pattern.search(text)
    if not match:
        raise InputError("no allowlisted relation found in evidence span")
    relation = match.group("relation").lower()
    subject = " ".join(match.group("subject").split()).strip()
    object_text = " ".join(match.group("object").split()).strip()
    object_text = re.sub(r"^than\s+", "", object_text, flags=re.IGNORECASE)
    object_text = re.sub(r"^[A-Za-z -]+\s+values\s+than\s+", "", object_text, flags=re.IGNORECASE)
    if not subject or not object_text or subject.casefold() in {"a", "an", "the"}:
        raise InputError("relation subject/object are underspecified")
    return {
        "value": relation,
        "unit": "",
        "display": relation,
        "subject": subject,
        "object": object_text,
    }


def _extract_relation(
    text: str,
    expected: object = None,
    expected_subject: object = None,
    expected_object: object = None,
) -> dict[str, str]:
    claim = extract_relation_claim(text)
    relation = claim["value"]
    subject = claim["subject"]
    object_text = claim["object"]
    if expected is not None and relation != str(expected).lower():
        raise InputError(f"relation mismatch: found {relation}, expected {expected}")
    if expected_subject is not None and subject.casefold() != str(expected_subject).strip().casefold():
        raise InputError("relation subject does not match the acquisition path")
    if expected_object is not None and object_text.casefold() != str(expected_object).strip().casefold():
        raise InputError("relation object does not match the acquisition path")
    return claim
