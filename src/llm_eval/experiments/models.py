"""Data models for experiment execution results."""

from dataclasses import dataclass
from typing import Any

from llm_eval.providers.models import ModelResponse
from llm_eval.results.models import EvaluationRun, TestResult


@dataclass(frozen=True)
class ExperimentResult:
    """Complete result of a single experiment execution.

    An experiment consists of:
    - the evaluation run metadata,
    - the raw response returned by the model provider,
    - the individual test results produced by evaluating that response.

    All test results must belong to the same evaluation run.
    """

    run: EvaluationRun
    response: ModelResponse
    test_results: tuple[TestResult, ...]

    def __post_init__(self) -> None:
        """Validate the experiment result components."""

        if not isinstance(self.run, EvaluationRun):
            raise TypeError("run must be an EvaluationRun")

        if not isinstance(self.response, ModelResponse):
            raise TypeError("response must be a ModelResponse")

        if not isinstance(self.test_results, tuple):
            raise TypeError("test_results must be a tuple")

        if not self.test_results:
            raise ValueError("test_results must not be empty")

        for result in self.test_results:
            if not isinstance(result, TestResult):
                raise TypeError("test_results must contain only TestResult instances")

            if result.run_id != self.run.run_id:
                raise ValueError(
                    "all test_results must belong to the same run "
                    f"(expected run_id={self.run.run_id!r}, "
                    f"got {result.run_id!r})"
                )

    def to_dict(self) -> dict[str, Any]:
        """Serialize the complete experiment result into a dictionary."""

        return {
            "run": self.run.to_dict(),
            "response": self.response.to_dict(),
            "test_results": [
                result.to_dict() for result in self.test_results
            ],
        }
