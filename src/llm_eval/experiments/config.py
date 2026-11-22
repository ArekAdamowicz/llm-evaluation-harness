"""Configuration models for experiment execution and evaluation."""

from __future__ import annotations

import math
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any


def _freeze_value(value: Any) -> Any:
    """Recursively freeze supported JSON-compatible container types.

    Supported values:
    - None, bool, int, float, str: returned unchanged
    - Mapping with string keys: converted to MappingProxyType
    - list, tuple: converted to tuple
    - set, frozenset: converted to frozenset

    Other types raise TypeError.
    """
    if value is None or isinstance(value, bool):
        return value

    if isinstance(value, (int, float, str)):
        return value

    if isinstance(value, Mapping):
        if not all(isinstance(key, str) for key in value):
            raise TypeError("Mapping keys must be strings")

        return MappingProxyType(
            {key: _freeze_value(item) for key, item in value.items()}
        )

    if isinstance(value, (list, tuple)):
        return tuple(_freeze_value(item) for item in value)

    if isinstance(value, (set, frozenset)):
        return frozenset(_freeze_value(item) for item in value)

    raise TypeError(f"Unsupported data type for freezing: {type(value).__name__}")


def _validate_non_empty_string(value: Any, field_name: str) -> None:
    """Validate that a value is a non-empty string."""
    if not isinstance(value, str):
        raise TypeError(f"{field_name} must be a string")

    if not value.strip():
        raise ValueError(f"{field_name} must not be empty")


def _validate_finite_number(
    value: Any,
    field_name: str,
    *,
    minimum: float | None = None,
    exclusive_minimum: bool = False,
) -> None:
    """Validate a finite numeric value, rejecting booleans."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{field_name} must be a number")

    try:
        is_finite = math.isfinite(value)
    except OverflowError:
        is_finite = False

    if not is_finite:
        raise ValueError(f"{field_name} must be finite")

    if minimum is not None:
        if exclusive_minimum and value <= minimum:
            raise ValueError(f"{field_name} must be greater than {minimum}")

        if not exclusive_minimum and value < minimum:
            raise ValueError(f"{field_name} must be at least {minimum}")


@dataclass(frozen=True)
class ExecutionConfig:
    """Configuration controlling code execution.

    The global timeout applies to the entire execution.
    Phase-specific timeouts optionally limit importing and function calls.
    A phase timeout of None means that only the global timeout applies.

    The subprocess execution mode is not a secure sandbox. It does not
    protect the filesystem, network, environment variables, or against
    privilege escalation. Docker should be considered for executing
    untrusted code in production environments.
    """

    timeout_seconds: float = 10.0
    import_timeout_seconds: float | None = None
    call_timeout_seconds: float | None = None
    memory_limit_mb: int | None = None
    sandbox_type: str = "subprocess"

    def __post_init__(self) -> None:
        for field_name in (
            "timeout_seconds",
            "import_timeout_seconds",
            "call_timeout_seconds",
        ):
            value = getattr(self, field_name)

            if field_name != "timeout_seconds" and value is None:
                continue

            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise TypeError(f"{field_name} must be a finite positive number")

            try:
                is_finite = math.isfinite(value)
            except OverflowError:
                is_finite = False

            if not is_finite:
                raise ValueError(f"{field_name} must be a finite positive number")

            if value <= 0:
                raise ValueError(f"{field_name} must be a finite positive number")

        if self.memory_limit_mb is not None:
            if isinstance(self.memory_limit_mb, bool) or not isinstance(
                self.memory_limit_mb, int
            ):
                raise TypeError("memory_limit_mb must be a positive integer or None")

            if self.memory_limit_mb <= 0:
                raise ValueError("memory_limit_mb must be a positive integer or None")

        if not isinstance(self.sandbox_type, str):
            raise TypeError("sandbox_type must be a string")

        if self.sandbox_type not in {"subprocess", "docker", "none"}:
            raise ValueError(
                "sandbox_type must be one of: 'subprocess', 'docker', 'none'"
            )


@dataclass(frozen=True)
class EvaluationConfig:
    """Configuration for evaluating model-generated outputs.

    Dataset-level tolerances take precedence over these global defaults.
    """

    numeric_rel_tol: float = 1e-9
    numeric_abs_tol: float = 1e-12
    exact_match_required: bool = False
    ignore_whitespace: bool = False
    custom_comparators: Mapping[str, Callable[..., Any]] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _validate_finite_number(
            self.numeric_rel_tol,
            "numeric_rel_tol",
            minimum=0,
        )
        _validate_finite_number(
            self.numeric_abs_tol,
            "numeric_abs_tol",
            minimum=0,
        )

        if not isinstance(self.exact_match_required, bool):
            raise TypeError("exact_match_required must be a boolean")

        if not isinstance(self.ignore_whitespace, bool):
            raise TypeError("ignore_whitespace must be a boolean")

        if not isinstance(self.custom_comparators, Mapping):
            raise TypeError("custom_comparators must be a Mapping")

        for name, comparator in self.custom_comparators.items():
            _validate_non_empty_string(name, "comparator name")

            if not callable(comparator):
                raise TypeError(f"Comparator '{name}' must be callable")

        object.__setattr__(
            self,
            "custom_comparators",
            MappingProxyType(dict(self.custom_comparators)),
        )


@dataclass(frozen=True)
class ExperimentConfig:
    """Configuration describing one evaluation experiment."""

    experiment_id: str
    dataset_id: str
    task_category: str
    prompt_source: str
    execution_config: ExecutionConfig
    evaluation_config: EvaluationConfig
    prompt_version: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _validate_non_empty_string(self.experiment_id, "experiment_id")
        _validate_non_empty_string(self.dataset_id, "dataset_id")
        _validate_non_empty_string(self.task_category, "task_category")
        _validate_non_empty_string(self.prompt_source, "prompt_source")

        if self.prompt_version is not None:
            _validate_non_empty_string(self.prompt_version, "prompt_version")

        if not isinstance(self.execution_config, ExecutionConfig):
            raise TypeError("execution_config must be an ExecutionConfig instance")

        if not isinstance(self.evaluation_config, EvaluationConfig):
            raise TypeError("evaluation_config must be an EvaluationConfig instance")

        if not isinstance(self.metadata, Mapping):
            raise TypeError("metadata must be a Mapping")

        object.__setattr__(
            self,
            "metadata",
            _freeze_value(self.metadata),
        )
