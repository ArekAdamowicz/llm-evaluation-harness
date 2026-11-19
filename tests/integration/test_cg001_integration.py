from pathlib import Path

import pytest

from llm_eval.datasets.loader import load_dataset
from llm_eval.evaluation.comparisons import assert_numeric_close
from llm_eval.reference.code_generation import calculate_average


# Load the dataset once for all test cases.
PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATASET_PATH = (
    PROJECT_ROOT / "datasets" / "code-generation" / "CG-001" / "dataset.json"
)
DATASET = load_dataset(DATASET_PATH)


@pytest.mark.parametrize(
    "case",
    DATASET.cases,
    ids=lambda case: case["id"],
)
def test_cg001_integration(case: dict):
    case_id = case["id"]
    input_data = case["input"]
    expected = case["expected"]

    # Execute the reference implementation.
    try:
        result = calculate_average(input_data)
        raised_exception = None
    except Exception as error:
        result = None
        raised_exception = error

    if expected["type"] == "exception":
        # Verify that an exception was raised.
        assert raised_exception is not None, (
            f"[{case_id}] Expected {expected['exception_class']}, "
            "but the function completed successfully."
        )

        # Verify the exception type.
        assert type(raised_exception).__name__ == expected["exception_class"], (
            f"[{case_id}] Expected exception "
            f"'{expected['exception_class']}', "
            f"got '{type(raised_exception).__name__}'."
        )

        # Verify the exception message.
        assert expected["message"] in str(raised_exception), (
            f"[{case_id}] Expected message containing "
            f"'{expected['message']}', "
            f"got '{str(raised_exception)}'."
        )

    elif expected["type"] == "numeric":
        # Verify that no exception was raised.
        assert raised_exception is None, (
            f"[{case_id}] Unexpected exception: "
            f"{type(raised_exception).__name__}: {raised_exception}"
        )

        # Compare the numerical result.
        assert_numeric_close(
            result,
            expected["value"],
            rel_tol=expected.get("rel_tol", 1e-9),
            abs_tol=expected.get("abs_tol", 1e-12),
        )

    else:
        pytest.fail(
            f"[{case_id}] Unknown expected result type: "
            f"{expected['type']}"
        )
