"""Unit tests for llm_eval.experiments.models."""

import json
from dataclasses import FrozenInstanceError
from datetime import datetime, timezone

import pytest

from llm_eval.experiments.models import ExperimentResult
from llm_eval.providers.models import ModelResponse
from llm_eval.results.models import (
    EvaluationRun,
    Metrics,
    ModelInfo,
    TestResult,
)


@pytest.fixture
def model_info():
    return ModelInfo(provider="manual", name="reference-like")


@pytest.fixture
def run():
    return EvaluationRun(
        run_id="run-001",
        dataset_id="CG-001",
        dataset_version="1.0",
        task_version="1.2",
    )


@pytest.fixture
def response(model_info):
    return ModelResponse(
        model_info=model_info,
        response_text="def calculate_average(numbers):\n    return sum(numbers) / len(numbers)",
        metrics=Metrics(latency_ms=12.5),
        timestamp=datetime.now(timezone.utc),
    )


@pytest.fixture
def test_results():
    return (
        TestResult(
            run_id="run-001",
            test_case_id="CG-001-F01",
        ),
        TestResult(
            run_id="run-001",
            test_case_id="CG-001-F02",
        ),
    )


@pytest.fixture
def experiment_result(run, response, test_results):
    return ExperimentResult(
        run=run,
        response=response,
        test_results=test_results,
    )


class TestExperimentResultValidation:
    def test_accepts_valid_components(self, experiment_result, run, response):
        assert experiment_result.run is run
        assert experiment_result.response is response
        assert len(experiment_result.test_results) == 2

    @pytest.mark.parametrize(
        ("field", "value"),
        [
            ("run", None),
            ("response", None),
            ("test_results", None),
        ],
    )
    def test_rejects_invalid_component_types(
        self,
        run,
        response,
        test_results,
        field,
        value,
    ):
        values = {
            "run": run,
            "response": response,
            "test_results": test_results,
        }
        values[field] = value

        with pytest.raises(TypeError):
            ExperimentResult(**values)

    def test_rejects_empty_test_results(self, run, response):
        with pytest.raises(ValueError):
            ExperimentResult(
                run=run,
                response=response,
                test_results=(),
            )

    def test_rejects_results_from_another_run(
        self,
        run,
        response,
    ):
        results = (
            TestResult(
                run_id="another-run",
                test_case_id="CG-001-F01",
            ),
        )

        with pytest.raises(ValueError):
            ExperimentResult(
                run=run,
                response=response,
                test_results=results,
            )

    def test_rejects_non_test_result_items(self, run, response):
        with pytest.raises(TypeError):
            ExperimentResult(
                run=run,
                response=response,
                test_results=("not a TestResult",),
            )

    def test_rejects_list_instead_of_tuple(self, run, response):
        with pytest.raises(TypeError, match="test_results must be a tuple"):
            ExperimentResult(
                run=run,
                response=response,
                test_results=[
                    TestResult(
                        run_id="run-001",
                        test_case_id="CG-001-F01",
                    )
                ],
            )

    @pytest.mark.parametrize(
        ("field", "value"),
        [
            ("run", "not an EvaluationRun"),
            ("response", "not a ModelResponse"),
        ],
    )
    def test_rejects_wrong_component_types(
        self,
        run,
        response,
        test_results,
        field,
        value,
    ):
        values = {
            "run": run,
            "response": response,
            "test_results": test_results,
        }
        values[field] = value

        with pytest.raises(TypeError):
            ExperimentResult(**values)

class TestExperimentResultImmutability:
    def test_dataclass_is_frozen(self, experiment_result):
        with pytest.raises(FrozenInstanceError):
            experiment_result.run = EvaluationRun()

    def test_test_results_are_stored_as_tuple(self, experiment_result):
        assert isinstance(experiment_result.test_results, tuple)


class TestExperimentResultSerialization:
    def test_serializes_nested_models(
        self,
        experiment_result,
        run,
        response,
    ):
        result = experiment_result.to_dict()

        assert result == {
            "run": run.to_dict(),
            "response": response.to_dict(),
            "test_results": [
                item.to_dict()
                for item in experiment_result.test_results
            ],
        }

    def test_serialization_produces_valid_json(self, experiment_result):
        payload = json.dumps(
            experiment_result.to_dict(),
            allow_nan=False,
        )

        assert isinstance(payload, str)
