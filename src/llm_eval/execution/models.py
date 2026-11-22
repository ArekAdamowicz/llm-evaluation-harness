import keyword
import math
from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import Enum
from types import MappingProxyType
from typing import Any

from llm_eval.experiments.config import ExecutionConfig
from llm_eval.results.models import ErrorInfo, ExceptionInfo


class ExecutionOutcome(str, Enum):
    SUCCESS = "success"
    EXCEPTION = "exception"
    IMPORT_ERROR = "import_error"
    TIMEOUT = "timeout"
    RESOURCE_LIMIT = "resource_limit"
    SERIALIZATION_ERROR = "serialization_error"
    INFRASTRUCTURE_ERROR = "infrastructure_error"


def _freeze_json_value(value: Any, path: str = "value") -> Any:
    """Validate and deeply freeze a JSON-compatible value."""
    if value is None or isinstance(value, (bool, int, str)):
        return value

    if isinstance(value, float):
        try:
            is_finite = math.isfinite(value)
        except OverflowError:
            is_finite = False

        if not is_finite:
            raise ValueError(f"{path} must be a finite number")

        return value

    if isinstance(value, list):
        return tuple(
            _freeze_json_value(item, f"{path}[{index}]")
            for index, item in enumerate(value)
        )

    if isinstance(value, Mapping):
        frozen: dict[str, Any] = {}

        for key, item in value.items():
            if not isinstance(key, str):
                raise TypeError(f"{path} mapping keys must be strings")

            frozen[key] = _freeze_json_value(item, f"{path}.{key}")

        return MappingProxyType(frozen)

    raise TypeError(
        f"{path} must contain only JSON-compatible values; got {type(value).__name__}"
    )


def _freeze_args(args: Any, path: str = "args") -> tuple[Any, ...]:
    """Validate and deeply freeze positional arguments."""
    if not isinstance(args, tuple):
        raise TypeError(f"{path} must be a tuple")

    return tuple(
        _freeze_json_value(value, f"{path}[{index}]")
        for index, value in enumerate(args)
    )


def _freeze_kwargs(kwargs: Any, path: str = "kwargs") -> Mapping[str, Any]:
    """Validate and deeply freeze keyword arguments."""
    if not isinstance(kwargs, Mapping):
        raise TypeError(f"{path} must be a mapping")

    frozen: dict[str, Any] = {}

    for key, value in kwargs.items():
        if not isinstance(key, str):
            raise TypeError(f"{path} keys must be strings")

        frozen[key] = _freeze_json_value(value, f"{path}.{key}")

    return MappingProxyType(frozen)


@dataclass(frozen=True)
class ExecutionMetrics:
    total_duration_ms: float
    import_duration_ms: float | None = None
    call_duration_ms: float | None = None

    def __post_init__(self) -> None:
        for name in (
            "total_duration_ms",
            "import_duration_ms",
            "call_duration_ms",
        ):
            value = getattr(self, name)

            if value is None and name != "total_duration_ms":
                continue

            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise TypeError(f"{name} must be a number")

            try:
                is_finite = math.isfinite(value)
            except OverflowError:
                is_finite = False

            if not is_finite:
                raise ValueError(f"{name} must be finite")

            if value < 0:
                raise ValueError(f"{name} must be non-negative")


@dataclass(frozen=True)
class ExecutionRequest:
    source_code: str
    entry_point: str
    config: ExecutionConfig
    args: tuple[Any, ...] = ()
    kwargs: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.source_code, str):
            raise TypeError("source_code must be a string")

        if not self.source_code.strip():
            raise ValueError("source_code must not be empty")

        if not isinstance(self.entry_point, str):
            raise TypeError("entry_point must be a string")

        if not self.entry_point.isidentifier() or keyword.iskeyword(self.entry_point):
            raise ValueError("entry_point must be a valid non-keyword identifier")

        if not isinstance(self.config, ExecutionConfig):
            raise TypeError("config must be an ExecutionConfig")

        object.__setattr__(self, "args", _freeze_args(self.args))
        object.__setattr__(self, "kwargs", _freeze_kwargs(self.kwargs))


@dataclass(frozen=True)
class ExecutionResult:
    outcome: ExecutionOutcome
    metrics: ExecutionMetrics
    sandbox_type: str
    return_value: Any | None = None
    args_after: tuple[Any, ...] | None = None
    kwargs_after: Mapping[str, Any] | None = None
    exception: ExceptionInfo | None = None
    error: ErrorInfo | None = None
    timed_out_phase: str | None = None
    stdout: str = ""
    stderr: str = ""
    exit_code: int | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.outcome, ExecutionOutcome):
            raise TypeError("outcome must be an ExecutionOutcome")

        if not isinstance(self.metrics, ExecutionMetrics):
            raise TypeError("metrics must be an ExecutionMetrics")

        if not isinstance(self.sandbox_type, str):
            raise TypeError("sandbox_type must be a string")

        if self.sandbox_type not in {"subprocess", "docker", "none"}:
            raise ValueError(
                "sandbox_type must be one of: 'subprocess', 'docker', 'none'"
            )

        if self.exception is not None and not isinstance(self.exception, ExceptionInfo):
            raise TypeError("exception must be an ExceptionInfo or None")

        if self.error is not None and not isinstance(self.error, ErrorInfo):
            raise TypeError("error must be an ErrorInfo or None")

        if self.outcome == ExecutionOutcome.SUCCESS:
            if self.exception is not None or self.error is not None:
                raise ValueError("SUCCESS cannot contain exception or error")

        elif self.outcome == ExecutionOutcome.EXCEPTION:
            if self.exception is None or self.error is not None:
                raise ValueError("EXCEPTION requires exception and forbids error")

        else:
            if self.error is None or self.exception is not None:
                raise ValueError(
                    f"{self.outcome.value} requires error and forbids exception"
                )

        if self.timed_out_phase is not None:
            if not isinstance(self.timed_out_phase, str):
                raise TypeError("timed_out_phase must be a string or None")

            if self.outcome != ExecutionOutcome.TIMEOUT:
                raise ValueError("timed_out_phase is only allowed for TIMEOUT")

            if self.timed_out_phase not in {"import", "call", "total"}:
                raise ValueError(
                    "timed_out_phase must be one of: 'import', 'call', 'total'"
                )

        if not isinstance(self.stdout, str):
            raise TypeError("stdout must be a string")

        if not isinstance(self.stderr, str):
            raise TypeError("stderr must be a string")

        if self.exit_code is not None and (
            isinstance(self.exit_code, bool) or not isinstance(self.exit_code, int)
        ):
            raise TypeError("exit_code must be an integer or None")

        if self.return_value is not None:
            object.__setattr__(
                self,
                "return_value",
                _freeze_json_value(self.return_value, "return_value"),
            )

        if self.args_after is not None:
            object.__setattr__(
                self,
                "args_after",
                _freeze_args(self.args_after, "args_after"),
            )

        if self.kwargs_after is not None:
            object.__setattr__(
                self,
                "kwargs_after",
                _freeze_kwargs(self.kwargs_after, "kwargs_after"),
            )
