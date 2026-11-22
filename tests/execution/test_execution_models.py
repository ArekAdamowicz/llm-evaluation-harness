import math
from dataclasses import FrozenInstanceError

import pytest

from llm_eval.execution import (
    ExecutionMetrics,
    ExecutionOutcome,
    ExecutionRequest,
    ExecutionResult,
)
from llm_eval.experiments.config import ExecutionConfig
from llm_eval.results.models import ErrorInfo, ExceptionInfo


@pytest.fixture
def config() -> ExecutionConfig:
    return ExecutionConfig()


@pytest.fixture
def exception_info() -> ExceptionInfo:
    return ExceptionInfo(
        exception_type="ValueError",
        message="invalid value",
        traceback="Traceback...",
    )


@pytest.fixture
def error_info() -> ErrorInfo:
    return ErrorInfo(
        error_type="ImportError",
        message="module not found",
    )


@pytest.fixture
def metrics() -> ExecutionMetrics:
    return ExecutionMetrics(
        total_duration_ms=10.0,
        import_duration_ms=2.0,
        call_duration_ms=8.0,
    )


def test_execution_outcome_contains_expected_values() -> None:
    assert {outcome.value for outcome in ExecutionOutcome} == {
        "success",
        "exception",
        "import_error",
        "timeout",
        "resource_limit",
        "serialization_error",
        "infrastructure_error",
    }


def test_execution_metrics_accept_valid_values() -> None:
    metrics = ExecutionMetrics(
        total_duration_ms=10,
        import_duration_ms=2,
        call_duration_ms=8,
    )

    assert metrics.total_duration_ms == 10
    assert metrics.import_duration_ms == 2
    assert metrics.call_duration_ms == 8


@pytest.mark.parametrize(
    "field",
    [
        "total_duration_ms",
        "import_duration_ms",
        "call_duration_ms",
    ],
)
@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
def test_execution_metrics_reject_non_finite_values(
    field: str,
    value: float,
) -> None:
    kwargs = {"total_duration_ms": 1}
    kwargs[field] = value

    with pytest.raises(ValueError):
        ExecutionMetrics(**kwargs)


@pytest.mark.parametrize(
    "field",
    [
        "total_duration_ms",
        "import_duration_ms",
        "call_duration_ms",
    ],
)
def test_execution_metrics_reject_bool(field: str) -> None:
    kwargs = {"total_duration_ms": 1}
    kwargs[field] = True

    with pytest.raises(TypeError):
        ExecutionMetrics(**kwargs)


@pytest.mark.parametrize(
    "field",
    [
        "total_duration_ms",
        "import_duration_ms",
        "call_duration_ms",
    ],
)
def test_execution_metrics_reject_negative_values(field: str) -> None:
    kwargs = {"total_duration_ms": 1}
    kwargs[field] = -1

    with pytest.raises(ValueError):
        ExecutionMetrics(**kwargs)


@pytest.mark.parametrize(
    "field",
    [
        "total_duration_ms",
        "import_duration_ms",
        "call_duration_ms",
    ],
)
def test_execution_metrics_reject_huge_values(field: str) -> None:
    kwargs = {"total_duration_ms": 1}
    kwargs[field] = 10**1000

    with pytest.raises(ValueError):
        ExecutionMetrics(**kwargs)


def test_execution_metrics_allow_none_for_optional_fields() -> None:
    metrics = ExecutionMetrics(total_duration_ms=0)

    assert metrics.import_duration_ms is None
    assert metrics.call_duration_ms is None


def test_execution_metrics_are_immutable() -> None:
    metrics = ExecutionMetrics(total_duration_ms=1)

    with pytest.raises(FrozenInstanceError):
        metrics.total_duration_ms = 2  # type: ignore[misc]


def test_execution_request_accepts_valid_data(config: ExecutionConfig) -> None:
    request = ExecutionRequest(
        source_code="def calculate(): return 42",
        entry_point="calculate",
        config=config,
        args=([1, 2],),
        kwargs={"options": {"enabled": True}},
    )
    assert request.source_code == "def calculate(): return 42"
    assert request.entry_point == "calculate"
    assert request.args == ((1, 2),)
    assert request.kwargs["options"]["enabled"] is True


@pytest.mark.parametrize("entry_point", ["class", "for", "return", "import"])
def test_execution_request_rejects_python_keywords(
    config: ExecutionConfig,
    entry_point: str,
) -> None:
    with pytest.raises(ValueError, match="non-keyword identifier"):
        ExecutionRequest(
            source_code="def calculate(): pass",
            entry_point=entry_point,
            config=config,
        )


@pytest.mark.parametrize(
    ("source_code", "entry_point", "expected_error"),
    [
        (None, "calculate", TypeError),
        ("   ", "calculate", ValueError),
        ("def calculate(): pass", None, TypeError),
        ("def calculate(): pass", "", ValueError),
        ("def calculate(): pass", "not valid", ValueError),
    ],
)
def test_execution_request_rejects_invalid_fields(
    config: ExecutionConfig,
    source_code: str,
    entry_point: str,
    expected_error: type[Exception],
) -> None:
    with pytest.raises(expected_error):
        ExecutionRequest(
            source_code=source_code,
            entry_point=entry_point,
            config=config,
        )


def test_execution_request_requires_execution_config() -> None:
    with pytest.raises(TypeError):
        ExecutionRequest(
            source_code="def calculate(): pass",
            entry_point="calculate",
            config=None,  # type: ignore[arg-type]
        )


def test_execution_request_requires_tuple_args(config: ExecutionConfig) -> None:
    with pytest.raises(TypeError):
        ExecutionRequest(
            source_code="def calculate(): pass",
            entry_point="calculate",
            config=config,
            args=[1, 2],  # type: ignore[arg-type]
        )


def test_execution_request_requires_mapping_kwargs(config: ExecutionConfig) -> None:
    with pytest.raises(TypeError):
        ExecutionRequest(
            source_code="def calculate(): pass",
            entry_point="calculate",
            config=config,
            kwargs=[("value", 1)],  # type: ignore[arg-type]
        )


@pytest.mark.parametrize(
    "value",
    [
        {1, 2},
        frozenset({1, 2}),
        object(),
        (1, 2),
    ],
)
def test_execution_request_rejects_non_json_values(
    config: ExecutionConfig,
    value: object,
) -> None:
    with pytest.raises(TypeError):
        ExecutionRequest(
            source_code="def calculate(): pass",
            entry_point="calculate",
            config=config,
            args=(value,),
        )


def test_execution_request_rejects_non_string_mapping_keys(
    config: ExecutionConfig,
) -> None:
    with pytest.raises(TypeError):
        ExecutionRequest(
            source_code="def calculate(): pass",
            entry_point="calculate",
            config=config,
            kwargs={1: "value"},  # type: ignore[dict-item]
        )


def test_execution_request_rejects_non_finite_float(
    config: ExecutionConfig,
) -> None:
    with pytest.raises(ValueError):
        ExecutionRequest(
            source_code="def calculate(): pass",
            entry_point="calculate",
            config=config,
            args=(math.nan,),
        )


def test_execution_request_deeply_freezes_nested_values(
    config: ExecutionConfig,
) -> None:
    original = {"items": [1, {"enabled": True}]}

    request = ExecutionRequest(
        source_code="def calculate(): pass",
        entry_point="calculate",
        config=config,
        kwargs=original,
    )

    original["items"].append(2)

    assert request.kwargs["items"] == (1, {"enabled": True})

    with pytest.raises(TypeError):
        request.kwargs["new"] = "value"  # type: ignore[index]

    with pytest.raises(TypeError):
        request.kwargs["items"][1]["enabled"] = False  # type: ignore[index]


def test_execution_result_accepts_success(
    metrics: ExecutionMetrics,
) -> None:
    result = ExecutionResult(
        outcome=ExecutionOutcome.SUCCESS,
        metrics=metrics,
        sandbox_type="subprocess",
        return_value=42,
    )

    assert result.outcome == ExecutionOutcome.SUCCESS
    assert result.return_value == 42
    assert result.exception is None
    assert result.error is None


def test_execution_result_allows_none_return_value(
    metrics: ExecutionMetrics,
) -> None:
    result = ExecutionResult(
        outcome=ExecutionOutcome.SUCCESS,
        metrics=metrics,
        sandbox_type="none",
        return_value=None,
    )

    assert result.return_value is None


def test_execution_result_accepts_exception(
    metrics: ExecutionMetrics,
    exception_info: ExceptionInfo,
) -> None:
    result = ExecutionResult(
        outcome=ExecutionOutcome.EXCEPTION,
        metrics=metrics,
        sandbox_type="subprocess",
        exception=exception_info,
    )

    assert result.exception == exception_info


@pytest.mark.parametrize(
    "outcome",
    [
        ExecutionOutcome.IMPORT_ERROR,
        ExecutionOutcome.TIMEOUT,
        ExecutionOutcome.RESOURCE_LIMIT,
        ExecutionOutcome.SERIALIZATION_ERROR,
        ExecutionOutcome.INFRASTRUCTURE_ERROR,
    ],
)
def test_execution_result_requires_error_for_engine_failures(
    metrics: ExecutionMetrics,
    outcome: ExecutionOutcome,
    error_info: ErrorInfo,
) -> None:
    result = ExecutionResult(
        outcome=outcome,
        metrics=metrics,
        sandbox_type="subprocess",
        error=error_info,
    )

    assert result.error == error_info


def test_execution_result_rejects_missing_exception(
    metrics: ExecutionMetrics,
) -> None:
    with pytest.raises(ValueError):
        ExecutionResult(
            outcome=ExecutionOutcome.EXCEPTION,
            metrics=metrics,
            sandbox_type="subprocess",
        )


def test_execution_result_rejects_missing_error(
    metrics: ExecutionMetrics,
) -> None:
    with pytest.raises(ValueError):
        ExecutionResult(
            outcome=ExecutionOutcome.IMPORT_ERROR,
            metrics=metrics,
            sandbox_type="subprocess",
        )


def test_execution_result_rejects_both_exception_and_error(
    metrics: ExecutionMetrics,
    exception_info: ExceptionInfo,
    error_info: ErrorInfo,
) -> None:
    with pytest.raises(ValueError):
        ExecutionResult(
            outcome=ExecutionOutcome.EXCEPTION,
            metrics=metrics,
            sandbox_type="subprocess",
            exception=exception_info,
            error=error_info,
        )


def test_execution_result_rejects_exception_for_success(
    metrics: ExecutionMetrics,
    exception_info: ExceptionInfo,
) -> None:
    with pytest.raises(ValueError):
        ExecutionResult(
            outcome=ExecutionOutcome.SUCCESS,
            metrics=metrics,
            sandbox_type="subprocess",
            exception=exception_info,
        )


def test_execution_result_rejects_invalid_sandbox_type(
    metrics: ExecutionMetrics,
) -> None:
    with pytest.raises(ValueError):
        ExecutionResult(
            outcome=ExecutionOutcome.SUCCESS,
            metrics=metrics,
            sandbox_type="unknown",
        )


@pytest.mark.parametrize("sandbox_type", [None, 123, [], {}])
def test_execution_result_rejects_invalid_sandbox_type_type(
    metrics: ExecutionMetrics,
    sandbox_type: object,
) -> None:
    with pytest.raises(TypeError, match="sandbox_type must be a string"):
        ExecutionResult(
            outcome=ExecutionOutcome.SUCCESS,
            metrics=metrics,
            sandbox_type=sandbox_type,
        )


@pytest.mark.parametrize("phase", ["import", "call", "total"])
def test_execution_result_accepts_timeout_phase(
    metrics: ExecutionMetrics,
    error_info: ErrorInfo,
    phase: str,
) -> None:
    result = ExecutionResult(
        outcome=ExecutionOutcome.TIMEOUT,
        metrics=metrics,
        sandbox_type="subprocess",
        error=error_info,
        timed_out_phase=phase,
    )

    assert result.timed_out_phase == phase


def test_execution_result_rejects_timeout_phase_for_non_timeout(
    metrics: ExecutionMetrics,
) -> None:
    with pytest.raises(ValueError):
        ExecutionResult(
            outcome=ExecutionOutcome.SUCCESS,
            metrics=metrics,
            sandbox_type="subprocess",
            timed_out_phase="call",
        )


def test_execution_result_rejects_invalid_timeout_phase(
    metrics: ExecutionMetrics,
    error_info: ErrorInfo,
) -> None:
    with pytest.raises(ValueError):
        ExecutionResult(
            outcome=ExecutionOutcome.TIMEOUT,
            metrics=metrics,
            sandbox_type="subprocess",
            error=error_info,
            timed_out_phase="unknown",
        )


@pytest.mark.parametrize("phase", [123, [], {}, True])
def test_execution_result_rejects_invalid_timeout_phase_type(
    metrics: ExecutionMetrics,
    error_info: ErrorInfo,
    phase: object,
) -> None:
    with pytest.raises(TypeError, match="timed_out_phase must be a string"):
        ExecutionResult(
            outcome=ExecutionOutcome.TIMEOUT,
            metrics=metrics,
            sandbox_type="subprocess",
            error=error_info,
            timed_out_phase=phase,
        )


def test_execution_result_validates_output_types(
    metrics: ExecutionMetrics,
) -> None:
    with pytest.raises(TypeError):
        ExecutionResult(
            outcome=ExecutionOutcome.SUCCESS,
            metrics=metrics,
            sandbox_type="none",
            stdout=123,  # type: ignore[arg-type]
        )

    with pytest.raises(TypeError):
        ExecutionResult(
            outcome=ExecutionOutcome.SUCCESS,
            metrics=metrics,
            sandbox_type="none",
            stderr=123,  # type: ignore[arg-type]
        )

    with pytest.raises(TypeError):
        ExecutionResult(
            outcome=ExecutionOutcome.SUCCESS,
            metrics=metrics,
            sandbox_type="none",
            exit_code=True,
        )


def test_execution_result_deeply_freezes_return_value(
    metrics: ExecutionMetrics,
) -> None:
    original = {"items": [1, 2]}

    result = ExecutionResult(
        outcome=ExecutionOutcome.SUCCESS,
        metrics=metrics,
        sandbox_type="none",
        return_value=original,
    )

    original["items"].append(3)

    assert result.return_value["items"] == (1, 2)


def test_execution_result_deeply_freezes_after_arguments(
    metrics: ExecutionMetrics,
) -> None:
    result = ExecutionResult(
        outcome=ExecutionOutcome.SUCCESS,
        metrics=metrics,
        sandbox_type="none",
        args_after=([1, 2],),
        kwargs_after={"items": [3, 4]},
    )

    assert result.args_after == ((1, 2),)
    assert result.kwargs_after["items"] == (3, 4)


def test_execution_result_rejects_non_json_return_value(
    metrics: ExecutionMetrics,
) -> None:
    with pytest.raises(TypeError):
        ExecutionResult(
            outcome=ExecutionOutcome.SUCCESS,
            metrics=metrics,
            sandbox_type="none",
            return_value={1, 2},
        )


def test_execution_result_rejects_non_json_after_arguments(
    metrics: ExecutionMetrics,
) -> None:
    with pytest.raises(TypeError):
        ExecutionResult(
            outcome=ExecutionOutcome.SUCCESS,
            metrics=metrics,
            sandbox_type="none",
            args_after=(object(),),
        )

    with pytest.raises(TypeError):
        ExecutionResult(
            outcome=ExecutionOutcome.SUCCESS,
            metrics=metrics,
            sandbox_type="none",
            kwargs_after={"value": object()},
        )


def test_execution_engine_protocol_has_execute_method() -> None:
    from llm_eval.execution import ExecutionEngine

    assert hasattr(ExecutionEngine, "execute")
