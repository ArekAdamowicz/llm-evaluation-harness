import json
import math

import pytest

from llm_eval.datasets.loader import DatasetLoadError, load_dataset

DATASET_PATH = "datasets/code-generation/CG-001/dataset.json"


def test_load_dataset_metadata():
    dataset = load_dataset(DATASET_PATH)

    assert dataset.schema_version == "1.0"
    assert dataset.dataset_id == "CG-001"
    assert dataset.dataset_version == "1.0"
    assert dataset.task_version == "1.2"
    assert len(dataset.cases) == 17


def test_load_dataset_case_ids_are_unique():
    dataset = load_dataset(DATASET_PATH)

    case_ids = [case["id"] for case in dataset.cases]

    assert len(case_ids) == len(set(case_ids))


def test_decode_tuple_tag():
    dataset = load_dataset(DATASET_PATH)

    case = next(case for case in dataset.cases if case["id"] == "CG-001-F06")

    assert case["input"] == (1, 2, 3)
    assert isinstance(case["input"], tuple)


def test_decode_huge_integer_tag():
    dataset = load_dataset(DATASET_PATH)

    case = next(case for case in dataset.cases if case["id"] == "CG-001-F17")

    assert isinstance(case["input"][0], int)
    assert len(str(case["input"][0])) == 401


def test_decode_integer_exceeding_python_string_conversion_limit(tmp_path):
    dataset_path = tmp_path / "dataset.json"
    integer_digits = "1" + ("0" * 5000)

    dataset = {
        "schema_version": "1.0",
        "dataset_id": "TEST-001",
        "dataset_version": "1.0",
        "task_version": "1.0",
        "description": "Large integer test",
        "cases": [
            {
                "id": "TEST-001-F01",
                "description": "Integer exceeding 4300 digits",
                "category": "numeric_stability",
                "input": [
                    {
                        "$type": "integer",
                        "value": integer_digits,
                    }
                ],
                "expected": {
                    "type": "numeric",
                    "value": 1,
                },
            }
        ],
    }

    dataset_path.write_text(
        json.dumps(dataset),
        encoding="utf-8",
    )

    loaded = load_dataset(dataset_path)

    assert loaded.cases[0]["input"][0] == 10**5000


def test_decode_special_float_tags():
    dataset = load_dataset(DATASET_PATH)

    nan_case = next(case for case in dataset.cases if case["id"] == "CG-001-F10")

    positive_inf_case = next(
        case for case in dataset.cases if case["id"] == "CG-001-F11"
    )

    negative_inf_case = next(
        case for case in dataset.cases if case["id"] == "CG-001-F12"
    )

    assert math.isnan(nan_case["input"][1])
    assert positive_inf_case["input"][1] == math.inf
    assert negative_inf_case["input"][1] == -math.inf


def test_load_dataset_rejects_unsupported_schema_version(tmp_path):
    dataset_path = tmp_path / "dataset.json"

    dataset_path.write_text(
        json.dumps(
            {
                "schema_version": "99.0",
                "dataset_id": "TEST-001",
                "dataset_version": "1.0",
                "task_version": "1.0",
                "description": "Test dataset",
                "cases": [],
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(DatasetLoadError, match="Unsupported schema version"):
        load_dataset(dataset_path)


def test_load_dataset_rejects_duplicate_case_ids(tmp_path):
    dataset_path = tmp_path / "dataset.json"

    case = {
        "id": "TEST-001-F01",
        "description": "Test case",
        "category": "basic_correctness",
        "input": [1, 2, 3],
        "expected": {
            "type": "numeric",
            "value": 2,
        },
    }

    dataset_path.write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "dataset_id": "TEST-001",
                "dataset_version": "1.0",
                "task_version": "1.0",
                "description": "Test dataset",
                "cases": [case, case],
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(DatasetLoadError, match="Duplicate case ID"):
        load_dataset(dataset_path)


def test_load_dataset_rejects_missing_required_field(tmp_path):
    dataset_path = tmp_path / "dataset.json"

    dataset_path.write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "dataset_id": "TEST-001",
                "dataset_version": "1.0",
                "task_version": "1.0",
                "cases": [],
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(DatasetLoadError, match="Missing dataset fields"):
        load_dataset(dataset_path)


def test_load_dataset_rejects_invalid_json(tmp_path):
    dataset_path = tmp_path / "dataset.json"
    dataset_path.write_text(
        '{"schema_version": "1.0", invalid}',
        encoding="utf-8",
    )

    with pytest.raises(DatasetLoadError, match="Invalid JSON"):
        load_dataset(dataset_path)


def test_load_dataset_rejects_missing_file(tmp_path):
    dataset_path = tmp_path / "missing.json"

    with pytest.raises(DatasetLoadError, match="Cannot read dataset file"):
        load_dataset(dataset_path)


def test_decode_nested_tagged_values(tmp_path):
    dataset_path = tmp_path / "dataset.json"

    dataset = {
        "schema_version": "1.0",
        "dataset_id": "TEST-001",
        "dataset_version": "1.0",
        "task_version": "1.0",
        "description": "Nested values test",
        "cases": [
            {
                "id": "TEST-001-F01",
                "description": "Nested tagged values",
                "category": "test",
                "input": [
                    {
                        "$type": "tuple",
                        "items": [
                            1,
                            {
                                "$type": "integer",
                                "value": "100000000000000000000",
                            },
                        ],
                    }
                ],
                "expected": {
                    "type": "numeric",
                    "value": 1,
                },
            }
        ],
    }

    dataset_path.write_text(
        json.dumps(dataset),
        encoding="utf-8",
    )

    loaded = load_dataset(dataset_path)

    decoded = loaded.cases[0]["input"][0]

    assert isinstance(decoded, tuple)
    assert decoded[0] == 1
    assert decoded[1] == 100000000000000000000


def test_decode_rejects_unknown_tag(tmp_path):
    dataset_path = tmp_path / "dataset.json"

    dataset = {
        "schema_version": "1.0",
        "dataset_id": "TEST-001",
        "dataset_version": "1.0",
        "task_version": "1.0",
        "description": "Unknown tag test",
        "cases": [
            {
                "id": "TEST-001-F01",
                "description": "Unknown tag",
                "category": "test",
                "input": [
                    {
                        "$type": "unknown",
                        "value": "something",
                    }
                ],
                "expected": {
                    "type": "numeric",
                    "value": 1,
                },
            }
        ],
    }

    dataset_path.write_text(
        json.dumps(dataset),
        encoding="utf-8",
    )

    with pytest.raises(DatasetLoadError, match="unknown tagged value type"):
        load_dataset(dataset_path)


def test_decode_rejects_invalid_integer_tag(tmp_path):
    dataset_path = tmp_path / "dataset.json"

    dataset = {
        "schema_version": "1.0",
        "dataset_id": "TEST-001",
        "dataset_version": "1.0",
        "task_version": "1.0",
        "description": "Invalid integer test",
        "cases": [
            {
                "id": "TEST-001-F01",
                "description": "Invalid integer",
                "category": "test",
                "input": [
                    {
                        "$type": "integer",
                        "value": "12.5",
                    }
                ],
                "expected": {
                    "type": "numeric",
                    "value": 1,
                },
            }
        ],
    }

    dataset_path.write_text(
        json.dumps(dataset),
        encoding="utf-8",
    )

    with pytest.raises(DatasetLoadError, match="invalid integer value"):
        load_dataset(dataset_path)


def test_decode_rejects_invalid_float_tag(tmp_path):
    dataset_path = tmp_path / "dataset.json"

    dataset = {
        "schema_version": "1.0",
        "dataset_id": "TEST-001",
        "dataset_version": "1.0",
        "task_version": "1.0",
        "description": "Invalid float test",
        "cases": [
            {
                "id": "TEST-001-F01",
                "description": "Invalid float",
                "category": "test",
                "input": [
                    {
                        "$type": "float",
                        "value": "not-a-float",
                    }
                ],
                "expected": {
                    "type": "numeric",
                    "value": 1,
                },
            }
        ],
    }

    dataset_path.write_text(
        json.dumps(dataset),
        encoding="utf-8",
    )

    with pytest.raises(DatasetLoadError, match="unsupported special float"):
        load_dataset(dataset_path)


def test_decode_rejects_non_string_float_value(tmp_path):
    dataset_path = tmp_path / "dataset.json"

    dataset = {
        "schema_version": "1.0",
        "dataset_id": "TEST-001",
        "dataset_version": "1.0",
        "task_version": "1.0",
        "description": "Invalid float type test",
        "cases": [
            {
                "id": "TEST-001-F01",
                "description": "Float value is not a string",
                "category": "test",
                "input": [
                    {
                        "$type": "float",
                        "value": [],
                    }
                ],
                "expected": {
                    "type": "numeric",
                    "value": 1,
                },
            }
        ],
    }

    dataset_path.write_text(
        json.dumps(dataset),
        encoding="utf-8",
    )

    with pytest.raises(DatasetLoadError, match="float 'value' must be a string"):
        load_dataset(dataset_path)


def _write_dataset_with_expected(tmp_path, expected):
    dataset_path = tmp_path / "dataset.json"

    dataset = {
        "schema_version": "1.0",
        "dataset_id": "TEST-001",
        "dataset_version": "1.0",
        "task_version": "1.0",
        "description": "Expected validation test",
        "cases": [
            {
                "id": "TEST-001-F01",
                "description": "Expected validation",
                "category": "test",
                "input": [1, 2, 3],
                "expected": expected,
            }
        ],
    }

    dataset_path.write_text(
        json.dumps(dataset),
        encoding="utf-8",
    )

    return dataset_path


def test_expected_rejects_unknown_type(tmp_path):
    path = _write_dataset_with_expected(
        tmp_path,
        {"type": "unknown"},
    )

    with pytest.raises(DatasetLoadError, match="Unsupported expected type"):
        load_dataset(path)


def test_expected_numeric_requires_value(tmp_path):
    path = _write_dataset_with_expected(
        tmp_path,
        {"type": "numeric"},
    )

    with pytest.raises(DatasetLoadError, match="numeric expected requires"):
        load_dataset(path)


def test_expected_numeric_rejects_boolean_value(tmp_path):
    path = _write_dataset_with_expected(
        tmp_path,
        {"type": "numeric", "value": True},
    )

    with pytest.raises(
        DatasetLoadError, match="numeric expected value must be a number"
    ):
        load_dataset(path)


def test_expected_numeric_rejects_string_value(tmp_path):
    path = _write_dataset_with_expected(
        tmp_path,
        {"type": "numeric", "value": "2.5"},
    )

    with pytest.raises(
        DatasetLoadError, match="numeric expected value must be a number"
    ):
        load_dataset(path)


def test_expected_numeric_rejects_negative_tolerance(tmp_path):
    path = _write_dataset_with_expected(
        tmp_path,
        {
            "type": "numeric",
            "value": 2.5,
            "rel_tol": -1e-9,
        },
    )

    with pytest.raises(DatasetLoadError, match="tolerances must be non-negative"):
        load_dataset(path)


def test_expected_numeric_rejects_non_finite_value(tmp_path):
    path = _write_dataset_with_expected(
        tmp_path,
        {
            "type": "numeric",
            "value": float("inf"),
        },
    )

    # Standard JSON does not support Infinity.
    # json.dumps produces a non-standard constant, which the loader rejects.
    with pytest.raises(DatasetLoadError, match="Non-standard JSON numeric constant"):
        load_dataset(path)


def test_expected_exception_requires_exception_class(tmp_path):
    path = _write_dataset_with_expected(
        tmp_path,
        {
            "type": "exception",
            "message": "numbers must not be empty",
        },
    )

    with pytest.raises(DatasetLoadError, match="exception expected requires"):
        load_dataset(path)


def test_expected_exception_requires_message(tmp_path):
    path = _write_dataset_with_expected(
        tmp_path,
        {
            "type": "exception",
            "exception_class": "ValueError",
        },
    )

    with pytest.raises(DatasetLoadError, match="exception expected requires"):
        load_dataset(path)
