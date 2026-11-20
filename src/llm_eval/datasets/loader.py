import json
import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

SUPPORTED_SCHEMA_VERSION = "1.0"


class DatasetLoadError(ValueError):
    """Raised when a dataset cannot be loaded or validated."""


@dataclass(frozen=True)
class Dataset:
    schema_version: str
    dataset_id: str
    dataset_version: str
    task_version: str
    description: str
    cases: list[dict[str, Any]]


def _require_non_empty_string(
    value: Any,
    field_name: str,
) -> str:
    if not isinstance(value, str) or not value.strip():
        raise DatasetLoadError(f"'{field_name}' must be a non-empty string")

    return value


def _parse_integer_string(value: str) -> int:
    """Parse a decimal integer string without Python's digit limit."""
    if not value:
        raise ValueError("invalid integer value")

    sign = 1
    if value[0] in "+-":
        if value[0] == "-":
            sign = -1
        value = value[1:]

    if not value or not all("0" <= char <= "9" for char in value):
        raise ValueError("invalid integer value")

    result = 0

    for index in range(0, len(value), 9):
        chunk = value[index : index + 9]
        result = result * (10 ** len(chunk)) + int(chunk)

    return sign * result


def _decode_tagged_value(
    value: Any,
    context: str = "input",
) -> Any:
    """Recursively decode explicitly tagged JSON values."""

    if isinstance(value, list):
        return [
            _decode_tagged_value(item, f"{context}[{index}]")
            for index, item in enumerate(value)
        ]

    if isinstance(value, dict):
        if "$type" not in value:
            return {
                key: _decode_tagged_value(item, f"{context}.{key}")
                for key, item in value.items()
            }

        tag = value["$type"]

        if not isinstance(tag, str):
            raise DatasetLoadError(f"{context}: '$type' must be a string")

        if tag == "tuple":
            if set(value) != {"$type", "items"}:
                raise DatasetLoadError(
                    f"{context}: tuple tag must contain only '$type' and 'items'"
                )

            items = value["items"]

            if not isinstance(items, list):
                raise DatasetLoadError(f"{context}: tuple 'items' must be a list")

            return tuple(
                _decode_tagged_value(item, f"{context}.items[{index}]")
                for index, item in enumerate(items)
            )

        if tag == "integer":
            if set(value) != {"$type", "value"}:
                raise DatasetLoadError(
                    f"{context}: integer tag must contain only '$type' and 'value'"
                )

            raw_value = value["value"]

            if not isinstance(raw_value, str):
                raise DatasetLoadError(
                    f"{context}: integer 'value' must be a decimal string"
                )

            if re.fullmatch(r"-?(0|[1-9][0-9]*)", raw_value) is None:
                raise DatasetLoadError(
                    f"{context}: invalid integer value '{raw_value}'"
                )

            try:
                return _parse_integer_string(raw_value)
            except ValueError as error:
                raise DatasetLoadError(
                    f"{context}: integer value cannot be decoded"
                ) from error

        if tag == "float":
            if set(value) != {"$type", "value"}:
                raise DatasetLoadError(
                    f"{context}: float tag must contain only '$type' and 'value'"
                )

            raw_value = value["value"]

            if not isinstance(raw_value, str):
                raise DatasetLoadError(f"{context}: float 'value' must be a string")

            special_floats = {
                "nan": math.nan,
                "inf": math.inf,
                "-inf": -math.inf,
            }

            if raw_value not in special_floats:
                raise DatasetLoadError(
                    f"{context}: unsupported special float '{raw_value}'"
                )

            return special_floats[raw_value]

        raise DatasetLoadError(f"{context}: unknown tagged value type '{tag}'")

    return value


def _reject_nonstandard_constant(value: str) -> None:
    raise DatasetLoadError(
        f"Non-standard JSON numeric constant '{value}'. "
        "Use an explicit tagged float instead."
    )


def _validate_expected(
    expected: Any,
    context: str,
) -> dict[str, Any]:
    if not isinstance(expected, dict):
        raise DatasetLoadError(f"{context} must be a JSON object")

    expected_type = expected.get("type")

    if expected_type == "numeric":
        if "value" not in expected:
            raise DatasetLoadError(f"{context}: numeric expected requires 'value'")

        value = expected["value"]

        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise DatasetLoadError(
                f"{context}: numeric expected value must be a number"
            )

        if isinstance(value, float) and not math.isfinite(value):
            raise DatasetLoadError(f"{context}: numeric expected value must be finite")

        for tolerance_name, default_value in (
            ("rel_tol", 1e-9),
            ("abs_tol", 1e-12),
        ):
            tolerance = expected.get(
                tolerance_name,
                default_value,
            )

            if isinstance(tolerance, bool) or not isinstance(tolerance, (int, float)):
                raise DatasetLoadError(
                    f"{context}: '{tolerance_name}' must be a number"
                )

            if (
                isinstance(tolerance, float) and not math.isfinite(tolerance)
            ) or tolerance < 0:
                raise DatasetLoadError(
                    f"{context}: tolerances must be non-negative and finite"
                )

        return expected

    if expected_type == "exception":
        exception_class = expected.get("exception_class")
        message = expected.get("message")

        if not isinstance(exception_class, str) or not exception_class.strip():
            raise DatasetLoadError(
                f"{context}: exception expected requires a non-empty 'exception_class'"
            )

        if not isinstance(message, str) or not message.strip():
            raise DatasetLoadError(
                f"{context}: exception expected requires a non-empty 'message'"
            )

        return expected

    raise DatasetLoadError(f"{context}: Unsupported expected type '{expected_type}'")


def _validate_dataset(data: Any) -> Dataset:
    if not isinstance(data, dict):
        raise DatasetLoadError("Dataset root must be a JSON object")

    required_fields = {
        "schema_version",
        "dataset_id",
        "dataset_version",
        "task_version",
        "description",
        "cases",
    }

    missing_fields = required_fields - data.keys()

    if missing_fields:
        raise DatasetLoadError(
            f"Missing dataset fields: {', '.join(sorted(missing_fields))}"
        )

    schema_version = _require_non_empty_string(data["schema_version"], "schema_version")

    if schema_version != SUPPORTED_SCHEMA_VERSION:
        raise DatasetLoadError(
            f"Unsupported schema version '{schema_version}'. "
            f"Supported version: '{SUPPORTED_SCHEMA_VERSION}'"
        )

    dataset_id = _require_non_empty_string(data["dataset_id"], "dataset_id")
    dataset_version = _require_non_empty_string(
        data["dataset_version"], "dataset_version"
    )
    task_version = _require_non_empty_string(data["task_version"], "task_version")
    description = _require_non_empty_string(data["description"], "description")

    raw_cases = data["cases"]

    if not isinstance(raw_cases, list) or not raw_cases:
        raise DatasetLoadError("'cases' must be a non-empty list")

    validated_cases = []
    seen_ids = set()

    required_case_fields = {
        "id",
        "description",
        "category",
        "input",
        "expected",
    }

    for index, case in enumerate(raw_cases):
        context = f"cases[{index}]"

        if not isinstance(case, dict):
            raise DatasetLoadError(f"{context} must be a JSON object")

        missing_case_fields = required_case_fields - case.keys()

        if missing_case_fields:
            raise DatasetLoadError(
                f"{context}: missing fields: {', '.join(sorted(missing_case_fields))}"
            )

        case_id = _require_non_empty_string(case["id"], f"{context}.id")

        if case_id in seen_ids:
            raise DatasetLoadError(f"Duplicate case ID '{case_id}'")

        seen_ids.add(case_id)

        case_description = _require_non_empty_string(
            case["description"], f"{context}.description"
        )

        category = _require_non_empty_string(case["category"], f"{context}.category")

        expected = _validate_expected(
            case["expected"],
            f"{context}.expected",
        )

        validated_cases.append(
            {
                **case,
                "description": case_description,
                "category": category,
                "input": _decode_tagged_value(case["input"], f"{context}.input"),
                "expected": expected,
            }
        )

    return Dataset(
        schema_version=schema_version,
        dataset_id=dataset_id,
        dataset_version=dataset_version,
        task_version=task_version,
        description=description,
        cases=validated_cases,
    )


def load_dataset(path: str | Path) -> Dataset:
    """Load, validate and decode a JSON dataset."""

    dataset_path = Path(path)

    try:
        content = dataset_path.read_text(encoding="utf-8")
    except OSError as error:
        raise DatasetLoadError(
            f"Cannot read dataset file '{dataset_path}': {error}"
        ) from error

    try:
        data = json.loads(
            content,
            parse_constant=_reject_nonstandard_constant,
        )
    except json.JSONDecodeError as error:
        raise DatasetLoadError(
            f"Invalid JSON in '{dataset_path}' "
            f"at line {error.lineno}, column {error.colno}: {error.msg}"
        ) from error

    return _validate_dataset(data)
