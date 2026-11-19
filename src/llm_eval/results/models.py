"""Data models for LLM evaluation results.

Design contract:
- dataclasses are frozen (historical results are facts, not state),
- nested containers are deeply frozen (dict -> mappingproxy, list -> tuple),
- to_dict() always produces standard-compliant JSON (allow_nan=False safe),
- actual_exception (result of running tested code) is NOT error
  (problem with the evaluation process itself).

Known limitation:
- list and tuple are indistinguishable after freezing.
  Dataset remains the source of truth for replay; TestResult is a record.
"""
from __future__ import annotations

import math
import uuid
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from types import MappingProxyType
from typing import Any


class TestStatus(str, Enum):
    """Outcome of a single test case execution."""

    PASS = "PASS"
    FAIL = "FAIL"
    ERROR = "ERROR"
    SKIPPED = "SKIPPED"

TestStatus.__test__ = False

# --------------------------------------------------------------------------
# helpers: defaults
# --------------------------------------------------------------------------


def _new_id() -> str:
    return str(uuid.uuid4())


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


# --------------------------------------------------------------------------
# helpers: deep immutability
# --------------------------------------------------------------------------

def _freeze_value(value: Any) -> Any:
    """Recursively convert mutable containers into immutable equivalents.

    Supported types (allowlist):
    - None, bool, int, float, str: returned as-is
    - Mapping (dict, etc.): recursively frozen, keys must be strings
    - list, tuple: recursively frozen to tuple
    - set, frozenset: recursively frozen to frozenset

    Any other type raises TypeError.

    Known limitation: list and tuple are indistinguishable after freezing.
    Dataset remains the source of truth for replay; TestResult is a record.
    """
    # Primitives - bool checked before int (bool is subclass of int)
    if value is None or isinstance(value, bool):
        return value
    if isinstance(value, (int, float, str)):
        return value

    # Mappings
    if isinstance(value, Mapping):
        if not all(isinstance(key, str) for key in value):
            raise TypeError("Mapping keys must be strings")
        return MappingProxyType(
            {key: _freeze_value(item) for key, item in value.items()}
        )

    # Sequences
    if isinstance(value, (list, tuple)):
        return tuple(_freeze_value(item) for item in value)

    # Sets
    if isinstance(value, (set, frozenset)):
        return frozenset(_freeze_value(item) for item in value)

    raise TypeError(
        f"Unsupported data type for freezing: {type(value).__name__}"
    )

def _thaw_value(value: Any) -> Any:
    """Inverse of _freeze_value (structure only, see docs for lossy cases)."""
    if isinstance(value, Mapping):
        return {key: _thaw_value(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_thaw_value(item) for item in value]
    if isinstance(value, frozenset):
        return sorted((_thaw_value(item) for item in value), key=repr)
    return value


# --------------------------------------------------------------------------
# helpers: JSON-safe serialization
# --------------------------------------------------------------------------


def _serialize_special_float(value: float) -> dict[str, Any] | float:
    """Tag NaN/Infinity exactly like the dataset format does."""
    if math.isnan(value):
        return {"$type": "float", "value": "nan"}
    if math.isinf(value):
        return {"$type": "float", "value": "inf" if value > 0 else "-inf"}
    return value


def _serialize_number(value: int | float | None) -> Any:
    """Serialize an optional scalar numeric field."""
    if value is None:
        return None
    if isinstance(value, float):
        return _serialize_special_float(value)
    return value


def _deep_serialize(value: Any) -> Any:
    """Recursively produce a JSON-compatible structure."""
    if isinstance(value, float):
        return _serialize_special_float(value)
    if isinstance(value, Mapping):
        return {key: _deep_serialize(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_deep_serialize(item) for item in value]
    if isinstance(value, frozenset):
        return sorted((_deep_serialize(item) for item in value), key=repr)
    return value


# --------------------------------------------------------------------------
# helpers: validation
# --------------------------------------------------------------------------


def _is_finite(value: int | float) -> bool:
    try:
        return math.isfinite(value)
    except OverflowError:
        # int too large to be represented as a float
        return False


def _validate_non_negative(value: float | int | None, field_name: str) -> None:
    """Value must be a finite, non-negative number (bool rejected)."""
    if value is None:
        return
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{field_name} must be a number")
    if not _is_finite(value):
        raise ValueError(f"{field_name} must be finite")
    if value < 0:
        raise ValueError(f"{field_name} must be non-negative, got {value}")


def _validate_non_negative_int(value: int | None, field_name: str) -> None:
    if value is None:
        return
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{field_name} must be an integer")
    if value < 0:
        raise ValueError(f"{field_name} must be non-negative, got {value}")


def _validate_finite_number(value: float | None, field_name: str) -> None:
    if value is None:
        return
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{field_name} must be a number")
    if not _is_finite(value):
        raise ValueError(f"{field_name} must be finite")


def _validate_range(
    value: float | None,
    field_name: str,
    min_value: float,
    max_value: float,
) -> None:
    if value is None:
        return
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{field_name} must be a number")
    if not _is_finite(value):
        raise ValueError(f"{field_name} must be finite")
    if not min_value <= value <= max_value:
        raise ValueError(
            f"{field_name} must be between {min_value} and {max_value}, "
            f"got {value}"
        )


def _validate_datetime(value: Any, field_name: str) -> None:
    if not isinstance(value, datetime):
        raise TypeError(f"{field_name} must be a datetime")
    if value.tzinfo is None or value.tzinfo.utcoffset(value) is None:
        raise ValueError(f"{field_name} must be timezone-aware")


def _validate_type(
    value: Any,
    expected: type,
    field_name: str,
    *,
    optional: bool = False,
) -> None:
    if value is None and optional:
        return
    if not isinstance(value, expected):
        raise TypeError(f"{field_name} must be a {expected.__name__}")


def _validate_non_empty_string(value: Any, field_name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string")


def _normalize_tags(tags: Any) -> tuple[str, ...]:
    if isinstance(tags, (str, bytes)):
        raise TypeError("tags must be a sequence of strings, not a string")
    try:
        normalized = tuple(tags)
    except TypeError as error:
        raise TypeError("tags must be an iterable of strings") from error
    if not all(isinstance(tag, str) for tag in normalized):
        raise TypeError("tags must contain only strings")
    return normalized


# --------------------------------------------------------------------------
# models
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class ModelInfo:
    """Snapshot of the model configuration used for a result."""

    provider: str
    name: str
    model_version: str | None = None
    temperature: float | None = None
    top_p: float | None = None
    seed: int | None = None

    def __post_init__(self) -> None:
        _validate_non_empty_string(self.provider, "provider")
        _validate_non_empty_string(self.name, "name")
        _validate_non_negative(self.temperature, "temperature")
        _validate_range(self.top_p, "top_p", 0.0, 1.0)
        if self.seed is not None and (
            isinstance(self.seed, bool) or not isinstance(self.seed, int)
        ):
            raise TypeError("seed must be an integer")

    def to_dict(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "name": self.name,
            "model_version": self.model_version,
            "temperature": _serialize_number(self.temperature),
            "top_p": _serialize_number(self.top_p),
            "seed": self.seed,
        }


@dataclass(frozen=True)
class Metrics:
    """Performance and cost metrics. Every field is optional."""

    latency_ms: float | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None
    estimated_cost: float | None = None
    cost_currency: str | None = None

    def __post_init__(self) -> None:
        _validate_non_negative(self.latency_ms, "latency_ms")
        _validate_non_negative(self.estimated_cost, "estimated_cost")
        _validate_non_negative_int(self.input_tokens, "input_tokens")
        _validate_non_negative_int(self.output_tokens, "output_tokens")
        _validate_non_negative_int(self.total_tokens, "total_tokens")

    def to_dict(self) -> dict[str, Any]:
        return {
            "latency_ms": _serialize_number(self.latency_ms),
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "total_tokens": self.total_tokens,
            "estimated_cost": _serialize_number(self.estimated_cost),
            "cost_currency": self.cost_currency,
        }


@dataclass(frozen=True)
class ExceptionInfo:
    """Exception raised by the code under test - a legitimate test outcome."""

    exception_type: str
    message: str
    traceback: str | None = None

    def __post_init__(self) -> None:
        _validate_non_empty_string(self.exception_type, "exception_type")
        if not isinstance(self.message, str):
            raise TypeError("message must be a string")

    def to_dict(self) -> dict[str, Any]:
        return {
            "exception_type": self.exception_type,
            "message": self.message,
            "traceback": self.traceback,
        }


@dataclass(frozen=True)
class ErrorInfo:
    """Problem with the evaluation process itself (API, parser, sandbox)."""

    error_type: str
    message: str
    details: str | None = None

    def __post_init__(self) -> None:
        _validate_non_empty_string(self.error_type, "error_type")
        if not isinstance(self.message, str):
            raise TypeError("message must be a string")

    def to_dict(self) -> dict[str, Any]:
        return {
            "error_type": self.error_type,
            "message": self.message,
            "details": self.details,
        }


@dataclass(frozen=True)
class TestResult:
    """Outcome of a single test case executed by a single model."""

    result_id: str = field(default_factory=_new_id)
    run_id: str = ""
    test_case_id: str = ""

    model_info: ModelInfo | None = None

    input_data: Any = field(default_factory=dict)
    rendered_prompt: str | None = None
    raw_output: str | None = None
    extracted_output: Any | None = None
    expected_output: Any = field(default_factory=dict)

    status: TestStatus = TestStatus.SKIPPED
    actual_result: Any | None = None
    actual_exception: ExceptionInfo | None = None
    error: ErrorInfo | None = None
    score: float | None = None

    metrics: Metrics = field(default_factory=Metrics)

    timestamp: datetime = field(default_factory=_utc_now)
    tags: tuple[str, ...] = ()
    metadata: Any = field(default_factory=dict)

    def __post_init__(self) -> None:
        # 1. types first - fail fast, before any attribute access
        _validate_type(self.status, TestStatus, "status")
        _validate_type(self.metrics, Metrics, "metrics")
        _validate_type(self.model_info, ModelInfo, "model_info", optional=True)
        _validate_type(
            self.actual_exception,
            ExceptionInfo,
            "actual_exception",
            optional=True,
        )
        _validate_type(self.error, ErrorInfo, "error", optional=True)
        _validate_datetime(self.timestamp, "timestamp")
        _validate_finite_number(self.score, "score")

        # 2. normalization
        object.__setattr__(self, "tags", _normalize_tags(self.tags))

        # 3. deep freeze
        for name in (
            "input_data",
            "extracted_output",
            "expected_output",
            "actual_result",
            "metadata",
        ):
            object.__setattr__(self, name, _freeze_value(getattr(self, name)))

        # 4. semantic consistency of status vs. error channels
        if self.status is TestStatus.ERROR:
            if self.error is None:
                raise ValueError("ERROR status requires error field to be set")
            if self.actual_exception is not None:
                raise ValueError(
                    "ERROR status must not contain actual_exception"
                )
        elif self.error is not None:
            raise ValueError("error field can only be set for ERROR status")

        if self.actual_exception is not None and self.status not in (
            TestStatus.PASS,
            TestStatus.FAIL,
        ):
            raise ValueError(
                "actual_exception can only be set for PASS or FAIL status"
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "result_id": self.result_id,
            "run_id": self.run_id,
            "test_case_id": self.test_case_id,
            "model_info": (
                self.model_info.to_dict() if self.model_info else None
            ),
            "input_data": _deep_serialize(self.input_data),
            "rendered_prompt": self.rendered_prompt,
            "raw_output": self.raw_output,
            "extracted_output": _deep_serialize(self.extracted_output),
            "expected_output": _deep_serialize(self.expected_output),
            "status": self.status.value,
            "actual_result": _deep_serialize(self.actual_result),
            "actual_exception": (
                self.actual_exception.to_dict()
                if self.actual_exception
                else None
            ),
            "error": self.error.to_dict() if self.error else None,
            "score": _serialize_number(self.score),
            "metrics": self.metrics.to_dict(),
            "timestamp": self.timestamp.isoformat(),
            "tags": list(self.tags),
            "metadata": _deep_serialize(self.metadata),
        }

TestResult.__test__ = False

@dataclass(frozen=True)
class EvaluationRun:
    """One experiment: a dataset version + model config + prompt template."""

    run_id: str = field(default_factory=_new_id)
    dataset_id: str = ""
    dataset_version: str = ""
    task_version: str = ""

    model_info: ModelInfo | None = None
    prompt_template: str | None = None

    started_at: datetime = field(default_factory=_utc_now)
    finished_at: datetime | None = None

    description: str = ""
    tags: tuple[str, ...] = ()
    metadata: Any = field(default_factory=dict)

    def __post_init__(self) -> None:
        _validate_type(self.model_info, ModelInfo, "model_info", optional=True)
        _validate_datetime(self.started_at, "started_at")
        if self.finished_at is not None:
            _validate_datetime(self.finished_at, "finished_at")

        object.__setattr__(self, "tags", _normalize_tags(self.tags))
        object.__setattr__(self, "metadata", _freeze_value(self.metadata))

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "dataset_id": self.dataset_id,
            "dataset_version": self.dataset_version,
            "task_version": self.task_version,
            "model_info": (
                self.model_info.to_dict() if self.model_info else None
            ),
            "prompt_template": self.prompt_template,
            "started_at": self.started_at.isoformat(),
            "finished_at": (
                self.finished_at.isoformat() if self.finished_at else None
            ),
            "description": self.description,
            "tags": list(self.tags),
            "metadata": _deep_serialize(self.metadata),
        }
