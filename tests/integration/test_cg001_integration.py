"""Integration test for CG-001 dataset with TestResult collection."""

from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

import pytest

from llm_eval.datasets.loader import load_dataset
from llm_eval.evaluation.comparisons import assert_numeric_close
from llm_eval.reference.code_generation import calculate_average
from llm_eval.results.models import (
    ErrorInfo,
    EvaluationRun,
    ExceptionInfo,
    TestResult,
    TestStatus,
)
from llm_eval.results.storage import save_run

# Load the dataset once for all test cases.
PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATASET_PATH = (
    PROJECT_ROOT / "datasets" / "code-generation" / "CG-001" / "dataset.json"
)
DATASET = load_dataset(DATASET_PATH)


@pytest.fixture(scope="module")
def evaluation_run():
    """Create one EvaluationRun for the entire test module."""
    return EvaluationRun(
        dataset_id=DATASET.dataset_id,
        dataset_version=DATASET.dataset_version,
        task_version=DATASET.task_version,
        description="CG-001 integration test with reference implementation",
    )


@pytest.fixture(scope="module")
def results_collector(evaluation_run):
    """Collect TestResult objects, generate report, and save to JSON."""
    results = []
    yield results
    
    # Teardown: create finished run, verify JSON, save, and print report
    finished_run = replace(
        evaluation_run,
        finished_at=datetime.now(timezone.utc),
    )
    
    # Save to JSON file
    results_root = PROJECT_ROOT / "results"
    saved_path = save_run(
        finished_run,
        results,
        results_root,
        task_category="code-generation",
    )
    
    # Print report
    _print_report(finished_run, results, saved_path)


def _print_report(run: EvaluationRun, results: list[TestResult], saved_path: Path) -> None:
    """Print evaluation report to console."""
    # Count statuses
    total = len(results)
    pass_count = sum(1 for r in results if r.status is TestStatus.PASS)
    fail_count = sum(1 for r in results if r.status is TestStatus.FAIL)
    error_count = sum(1 for r in results if r.status is TestStatus.ERROR)
    skipped_count = sum(1 for r in results if r.status is TestStatus.SKIPPED)
    
    print("\n")
    print("CG-001 Evaluation Report")
    print("=" * 24)
    print(f"Run ID: {run.run_id}")
    print(f"Saved to: {saved_path}")
    print()
    print(f"Total cases: {total}")
    print(f"PASS:        {pass_count:>2}")
    print(f"FAIL:        {fail_count:>2}")
    print(f"ERROR:       {error_count:>2}")
    print(f"SKIPPED:     {skipped_count:>2}")
    print()
    
    # Failed cases
    failed = [r for r in results if r.status is TestStatus.FAIL]
    print("Failed cases:")
    if failed:
        for r in failed:
            print(f"  - {r.test_case_id}:")
            if r.actual_exception:
                print(f"      Exception: {r.actual_exception.exception_type}: {r.actual_exception.message}")
            else:
                print(f"      Expected: {r.expected_output}")
                print(f"      Actual: {r.actual_result}")
    else:
        print("  None")
    print()
    
    # Error cases
    errors = [r for r in results if r.status is TestStatus.ERROR]
    print("Evaluation errors:")
    if errors:
        for r in errors:
            print(f"  - {r.test_case_id}: {r.error.error_type}: {r.error.message}")
    else:
        print("  None")


@pytest.mark.parametrize(
    "case",
    DATASET.cases,
    ids=lambda case: case["id"],
)
def test_cg001_integration(case: dict, evaluation_run: EvaluationRun, results_collector: list[TestResult]):
    """Test single case and collect TestResult."""
    case_id = case["id"]
    input_data = case["input"]
    expected = case["expected"]
    
    # Common fields for TestResult
    common_fields = {
        "run_id": evaluation_run.run_id,
        "test_case_id": case_id,
        "input_data": {"numbers": input_data},
        "expected_output": expected,
        "tags": [case["category"]],
    }
    
    # 1. Execute the reference implementation
    try:
        result = calculate_average(input_data)
        raised_exception = None
    except Exception as error:
        result = None
        raised_exception = error
    
    # 2. Create TestResult BEFORE assertion
    if expected["type"] == "exception":
        if raised_exception is not None:
            # Check if exception matches expectations
            exception_matches = (
                type(raised_exception).__name__ == expected["exception_class"]
                and expected["message"] in str(raised_exception)
            )
            status = TestStatus.PASS if exception_matches else TestStatus.FAIL
            test_result = TestResult(
                **common_fields,
                status=status,
                actual_exception=ExceptionInfo(
                    exception_type=type(raised_exception).__name__,
                    message=str(raised_exception),
                ),
            )
        else:
            test_result = TestResult(
                **common_fields,
                status=TestStatus.FAIL,
                actual_result=result,
            )
    elif expected["type"] == "numeric":
        if raised_exception is not None:
            test_result = TestResult(
                **common_fields,
                status=TestStatus.FAIL,
                actual_exception=ExceptionInfo(
                    exception_type=type(raised_exception).__name__,
                    message=str(raised_exception),
                ),
            )
        else:
            # Check if result matches expectations
            try:
                assert_numeric_close(
                    result,
                    expected["value"],
                    rel_tol=expected.get("rel_tol", 1e-9),
                    abs_tol=expected.get("abs_tol", 1e-12),
                )
                test_result = TestResult(
                    **common_fields,
                    status=TestStatus.PASS,
                    actual_result=result,
                )
            except AssertionError:
                test_result = TestResult(
                    **common_fields,
                    status=TestStatus.FAIL,
                    actual_result=result,
                )
    else:
        # Add ErrorInfo for unknown type
        test_result = TestResult(
            **common_fields,
            status=TestStatus.ERROR,
            error=ErrorInfo(
                error_type="UnknownExpectedType",
                message=f"Unknown expected result type: {expected['type']}",
            ),
        )
    
    # 3. Add TestResult to collector
    results_collector.append(test_result)
    
    # 4. Now perform pytest assertion
    if expected["type"] == "exception":
        assert raised_exception is not None, (
            f"[{case_id}] Expected {expected['exception_class']}, "
            "but the function completed successfully."
        )
        assert type(raised_exception).__name__ == expected["exception_class"], (
            f"[{case_id}] Expected exception "
            f"'{expected['exception_class']}', "
            f"got '{type(raised_exception).__name__}'."
        )
        assert expected["message"] in str(raised_exception), (
            f"[{case_id}] Expected message containing "
            f"'{expected['message']}', "
            f"got '{str(raised_exception)}'."
        )
    elif expected["type"] == "numeric":
        assert raised_exception is None, (
            f"[{case_id}] Unexpected exception: "
            f"{type(raised_exception).__name__}: {raised_exception}"
        )
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
