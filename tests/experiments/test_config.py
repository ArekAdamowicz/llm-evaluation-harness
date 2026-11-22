"""Tests for experiment configuration models."""

from dataclasses import FrozenInstanceError
from types import MappingProxyType

import pytest

from llm_eval.experiments.config import (
    EvaluationConfig,
    ExecutionConfig,
    ExperimentConfig,
)


class TestExecutionConfig:
    def test_default_values(self):
        config = ExecutionConfig()

        assert config.timeout_seconds == 10.0
        assert config.memory_limit_mb is None
        assert config.sandbox_type == "subprocess"

    def test_custom_values(self):
        config = ExecutionConfig(
            timeout_seconds=5.5,
            memory_limit_mb=256,
            sandbox_type="docker",
        )

        assert config.timeout_seconds == 5.5
        assert config.memory_limit_mb == 256
        assert config.sandbox_type == "docker"

    @pytest.mark.parametrize(
        "timeout",
        [0, -1, -0.1],
    )
    def test_rejects_non_positive_timeout(self, timeout):
        with pytest.raises(ValueError):
            ExecutionConfig(timeout_seconds=timeout)

    @pytest.mark.parametrize(
        "timeout",
        [True, False, "10", None],
    )
    def test_rejects_invalid_timeout_type(self, timeout):
        with pytest.raises(TypeError):
            ExecutionConfig(timeout_seconds=timeout)

    @pytest.mark.parametrize(
        "timeout",
        [float("nan"), float("inf"), float("-inf"), 10**1000],
    )
    def test_rejects_non_finite_timeout(self, timeout):
        with pytest.raises(ValueError):
            ExecutionConfig(timeout_seconds=timeout)

    @pytest.mark.parametrize(
        "memory_limit",
        [0, -1],
    )
    def test_rejects_non_positive_memory_limit(self, memory_limit):
        with pytest.raises(ValueError):
            ExecutionConfig(memory_limit_mb=memory_limit)

    @pytest.mark.parametrize(
        "memory_limit",
        [True, False, 128.5, "256"],
    )
    def test_rejects_invalid_memory_limit_type(self, memory_limit):
        with pytest.raises(TypeError):
            ExecutionConfig(memory_limit_mb=memory_limit)

    def test_accepts_none_memory_limit(self):
        config = ExecutionConfig(memory_limit_mb=None)

        assert config.memory_limit_mb is None

    @pytest.mark.parametrize(
        "sandbox_type",
        ["subprocess", "docker", "none"],
    )
    def test_accepts_supported_sandbox_types(self, sandbox_type):
        config = ExecutionConfig(sandbox_type=sandbox_type)

        assert config.sandbox_type == sandbox_type

    def test_rejects_unsupported_sandbox_type(self):
        with pytest.raises(ValueError):
            ExecutionConfig(sandbox_type="virtual_machine")

    def test_rejects_non_string_sandbox_type(self):
        with pytest.raises(TypeError):
            ExecutionConfig(sandbox_type=None)

    def test_configuration_is_immutable(self):
        config = ExecutionConfig()

        with pytest.raises(FrozenInstanceError):
            config.timeout_seconds = 20.0


class TestEvaluationConfig:
    def test_default_values(self):
        config = EvaluationConfig()

        assert config.numeric_rel_tol == 1e-9
        assert config.numeric_abs_tol == 1e-12
        assert config.exact_match_required is False
        assert config.ignore_whitespace is False
        assert config.custom_comparators == {}

    def test_accepts_custom_values(self):
        def comparator(actual, expected):
            return actual == expected

        config = EvaluationConfig(
            numeric_rel_tol=1e-5,
            numeric_abs_tol=1e-8,
            exact_match_required=True,
            ignore_whitespace=True,
            custom_comparators={"custom": comparator},
        )

        assert config.numeric_rel_tol == 1e-5
        assert config.numeric_abs_tol == 1e-8
        assert config.exact_match_required is True
        assert config.ignore_whitespace is True
        assert config.custom_comparators["custom"] is comparator

    @pytest.mark.parametrize(
        "field_name",
        ["numeric_rel_tol", "numeric_abs_tol"],
    )
    @pytest.mark.parametrize(
        "value",
        [-1, -0.1],
    )
    def test_rejects_negative_tolerances(self, field_name, value):
        with pytest.raises(ValueError):
            EvaluationConfig(**{field_name: value})

    @pytest.mark.parametrize(
        "field_name",
        ["numeric_rel_tol", "numeric_abs_tol"],
    )
    @pytest.mark.parametrize(
        "value",
        [True, False, "0.1", None],
    )
    def test_rejects_invalid_tolerance_types(self, field_name, value):
        with pytest.raises(TypeError):
            EvaluationConfig(**{field_name: value})

    @pytest.mark.parametrize(
        "field_name",
        ["numeric_rel_tol", "numeric_abs_tol"],
    )
    @pytest.mark.parametrize(
        "value",
        [float("nan"), float("inf"), float("-inf")],
    )
    def test_rejects_non_finite_tolerances(self, field_name, value):
        with pytest.raises(ValueError):
            EvaluationConfig(**{field_name: value})

    @pytest.mark.parametrize(
        "field_name",
        ["exact_match_required", "ignore_whitespace"],
    )
    @pytest.mark.parametrize(
        "value",
        [1, 0, "true", None],
    )
    def test_rejects_non_boolean_flags(self, field_name, value):
        with pytest.raises(TypeError):
            EvaluationConfig(**{field_name: value})

    def test_custom_comparators_are_read_only(self):
        def comparator(actual, expected):
            return actual == expected

        config = EvaluationConfig(custom_comparators={"custom": comparator})

        assert isinstance(config.custom_comparators, MappingProxyType)

        with pytest.raises(TypeError):
            config.custom_comparators["another"] = comparator

    def test_custom_comparator_identity_is_preserved(self):
        def comparator(actual, expected):
            return actual == expected

        config = EvaluationConfig(custom_comparators={"custom": comparator})

        assert config.custom_comparators["custom"] is comparator

    def test_rejects_non_mapping_comparators(self):
        with pytest.raises(TypeError):
            EvaluationConfig(custom_comparators=[])

    @pytest.mark.parametrize(
        "name",
        ["", " ", "\t"],
    )
    def test_rejects_empty_comparator_names(self, name):
        with pytest.raises(ValueError):
            EvaluationConfig(custom_comparators={name: lambda a, b: True})

    def test_rejects_non_string_comparator_names(self):
        with pytest.raises(TypeError):
            EvaluationConfig(custom_comparators={1: lambda a, b: True})

    def test_rejects_non_callable_comparator(self):
        with pytest.raises(TypeError):
            EvaluationConfig(custom_comparators={"custom": "not callable"})

    def test_configuration_is_immutable(self):
        config = EvaluationConfig()

        with pytest.raises(FrozenInstanceError):
            config.numeric_rel_tol = 0.1


class TestExperimentConfig:
    @pytest.fixture
    def valid_config(self):
        return ExperimentConfig(
            experiment_id="experiment-001",
            dataset_id="CG-001",
            task_category="code-generation",
            prompt_source="docs/test-cases/prompts/CG-001_v1.0.txt",
            execution_config=ExecutionConfig(),
            evaluation_config=EvaluationConfig(),
        )

    def test_accepts_valid_configuration(self, valid_config):
        assert valid_config.experiment_id == "experiment-001"
        assert valid_config.dataset_id == "CG-001"
        assert valid_config.task_category == "code-generation"
        assert valid_config.prompt_source == "docs/test-cases/prompts/CG-001_v1.0.txt"
        assert isinstance(valid_config.execution_config, ExecutionConfig)
        assert isinstance(valid_config.evaluation_config, EvaluationConfig)

    def test_default_values(self, valid_config):
        assert valid_config.prompt_version is None
        assert valid_config.metadata == {}

    def test_accepts_prompt_version_and_metadata(self):
        config = ExperimentConfig(
            experiment_id="experiment-001",
            dataset_id="CG-001",
            task_category="code-generation",
            prompt_source="prompt.txt",
            execution_config=ExecutionConfig(),
            evaluation_config=EvaluationConfig(),
            prompt_version="1.0",
            metadata={"environment": "development"},
        )

        assert config.prompt_version == "1.0"
        assert config.metadata["environment"] == "development"

    @pytest.mark.parametrize(
        "field_name",
        [
            "experiment_id",
            "dataset_id",
            "task_category",
            "prompt_source",
        ],
    )
    @pytest.mark.parametrize(
        "value",
        ["", " ", "\t"],
    )
    def test_rejects_empty_required_strings(
        self,
        field_name,
        value,
    ):
        values = {
            "experiment_id": "experiment-001",
            "dataset_id": "CG-001",
            "task_category": "code-generation",
            "prompt_source": "prompt.txt",
            "execution_config": ExecutionConfig(),
            "evaluation_config": EvaluationConfig(),
        }
        values[field_name] = value

        with pytest.raises(ValueError):
            ExperimentConfig(**values)

    @pytest.mark.parametrize(
        "field_name",
        [
            "experiment_id",
            "dataset_id",
            "task_category",
            "prompt_source",
        ],
    )
    def test_rejects_non_string_required_fields(self, field_name):
        values = {
            "experiment_id": "experiment-001",
            "dataset_id": "CG-001",
            "task_category": "code-generation",
            "prompt_source": "prompt.txt",
            "execution_config": ExecutionConfig(),
            "evaluation_config": EvaluationConfig(),
        }
        values[field_name] = None

        with pytest.raises(TypeError):
            ExperimentConfig(**values)

    @pytest.mark.parametrize(
        "prompt_version",
        ["", " ", "\t"],
    )
    def test_rejects_empty_prompt_version(self, prompt_version):
        with pytest.raises(ValueError):
            ExperimentConfig(
                experiment_id="experiment-001",
                dataset_id="CG-001",
                task_category="code-generation",
                prompt_source="prompt.txt",
                execution_config=ExecutionConfig(),
                evaluation_config=EvaluationConfig(),
                prompt_version=prompt_version,
            )

    def test_rejects_non_string_prompt_version(self):
        with pytest.raises(TypeError):
            ExperimentConfig(
                experiment_id="experiment-001",
                dataset_id="CG-001",
                task_category="code-generation",
                prompt_source="prompt.txt",
                execution_config=ExecutionConfig(),
                evaluation_config=EvaluationConfig(),
                prompt_version=1.0,
            )

    def test_rejects_invalid_execution_config(self):
        with pytest.raises(TypeError):
            ExperimentConfig(
                experiment_id="experiment-001",
                dataset_id="CG-001",
                task_category="code-generation",
                prompt_source="prompt.txt",
                execution_config={},
                evaluation_config=EvaluationConfig(),
            )

    def test_rejects_invalid_evaluation_config(self):
        with pytest.raises(TypeError):
            ExperimentConfig(
                experiment_id="experiment-001",
                dataset_id="CG-001",
                task_category="code-generation",
                prompt_source="prompt.txt",
                execution_config=ExecutionConfig(),
                evaluation_config={},
            )

    def test_rejects_non_mapping_metadata(self):
        with pytest.raises(TypeError):
            ExperimentConfig(
                experiment_id="experiment-001",
                dataset_id="CG-001",
                task_category="code-generation",
                prompt_source="prompt.txt",
                execution_config=ExecutionConfig(),
                evaluation_config=EvaluationConfig(),
                metadata=[],
            )

    def test_metadata_is_deeply_immutable(self):
        nested_metadata = {
            "environment": {
                "tags": ["test", "development"],
                "options": {"verbose"},
            }
        }

        config = ExperimentConfig(
            experiment_id="experiment-001",
            dataset_id="CG-001",
            task_category="code-generation",
            prompt_source="prompt.txt",
            execution_config=ExecutionConfig(),
            evaluation_config=EvaluationConfig(),
            metadata=nested_metadata,
        )

        assert isinstance(config.metadata, MappingProxyType)
        assert isinstance(config.metadata["environment"], MappingProxyType)
        assert config.metadata["environment"]["tags"] == (
            "test",
            "development",
        )
        assert config.metadata["environment"]["options"] == frozenset({"verbose"})

        with pytest.raises(TypeError):
            config.metadata["new"] = "value"

        with pytest.raises(TypeError):
            config.metadata["environment"]["new"] = "value"

    def test_metadata_accepts_mapping_proxy(self):
        metadata = MappingProxyType({"source": "test"})

        config = ExperimentConfig(
            experiment_id="experiment-001",
            dataset_id="CG-001",
            task_category="code-generation",
            prompt_source="prompt.txt",
            execution_config=ExecutionConfig(),
            evaluation_config=EvaluationConfig(),
            metadata=metadata,
        )

        assert config.metadata["source"] == "test"

    def test_configuration_is_immutable(self, valid_config):
        with pytest.raises(FrozenInstanceError):
            valid_config.experiment_id = "another-experiment"

    def test_rejects_non_string_metadata_keys(self):
        with pytest.raises(
            TypeError,
            match="Mapping keys must be strings",
        ):
            ExperimentConfig(
                experiment_id="experiment-001",
                dataset_id="CG-001",
                task_category="code-generation",
                prompt_source="prompt.txt",
                execution_config=ExecutionConfig(),
                evaluation_config=EvaluationConfig(),
                metadata={1: "value"},
            )

    def test_rejects_non_string_nested_metadata_keys(self):
        with pytest.raises(
            TypeError,
            match="Mapping keys must be strings",
        ):
            ExperimentConfig(
                experiment_id="experiment-001",
                dataset_id="CG-001",
                task_category="code-generation",
                prompt_source="prompt.txt",
                execution_config=ExecutionConfig(),
                evaluation_config=EvaluationConfig(),
                metadata={"nested": {1: "value"}},
            )

    def test_rejects_unsupported_metadata_value(self):
        class CustomObject:
            pass

        with pytest.raises(
            TypeError,
            match="Unsupported data type",
        ):
            ExperimentConfig(
                experiment_id="experiment-001",
                dataset_id="CG-001",
                task_category="code-generation",
                prompt_source="prompt.txt",
                execution_config=ExecutionConfig(),
                evaluation_config=EvaluationConfig(),
                metadata={"custom": CustomObject()},
            )

    @pytest.mark.parametrize(
        ("field", "value"),
        [
            ("import_timeout_seconds", None),
            ("call_timeout_seconds", None),
            ("import_timeout_seconds", 1),
            ("import_timeout_seconds", 0.5),
            ("call_timeout_seconds", 2),
            ("call_timeout_seconds", 0.25),
        ],
    )
    def test_accepts_valid_phase_timeouts(
        self,
        field: str,
        value: float | None,
    ) -> None:
        config = ExecutionConfig(**{field: value})

        assert getattr(config, field) == value

    @pytest.mark.parametrize(
        ("field", "value"),
        [
            ("import_timeout_seconds", 0),
            ("import_timeout_seconds", -1),
            ("import_timeout_seconds", -0.5),
            ("call_timeout_seconds", 0),
            ("call_timeout_seconds", -1),
            ("call_timeout_seconds", -0.5),
            ("import_timeout_seconds", True),
            ("import_timeout_seconds", False),
            ("call_timeout_seconds", True),
            ("call_timeout_seconds", False),
            ("import_timeout_seconds", "1"),
            ("call_timeout_seconds", "1"),
            ("import_timeout_seconds", float("nan")),
            ("import_timeout_seconds", float("inf")),
            ("import_timeout_seconds", float("-inf")),
            ("call_timeout_seconds", float("nan")),
            ("call_timeout_seconds", float("inf")),
            ("call_timeout_seconds", float("-inf")),
            ("import_timeout_seconds", 10**1000),
            ("call_timeout_seconds", 10**1000),
        ],
    )
    def test_rejects_invalid_phase_timeouts(
        self,
        field: str,
        value: object,
    ) -> None:
        with pytest.raises((TypeError, ValueError)):
            ExecutionConfig(**{field: value})

    def test_phase_timeouts_are_independent(self) -> None:
        import_only = ExecutionConfig(import_timeout_seconds=2.5)
        call_only = ExecutionConfig(call_timeout_seconds=3.5)

        assert import_only.import_timeout_seconds == 2.5
        assert import_only.call_timeout_seconds is None

        assert call_only.import_timeout_seconds is None
        assert call_only.call_timeout_seconds == 3.5

    def test_phase_timeouts_are_immutable(self) -> None:
        config = ExecutionConfig(
            import_timeout_seconds=2.5,
            call_timeout_seconds=3.5,
        )

        with pytest.raises(FrozenInstanceError):
            config.import_timeout_seconds = 5.0

        with pytest.raises(FrozenInstanceError):
            config.call_timeout_seconds = 5.0
