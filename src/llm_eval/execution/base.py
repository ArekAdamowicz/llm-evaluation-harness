from typing import Protocol

from llm_eval.execution.models import ExecutionRequest, ExecutionResult


class ExecutionEngine(Protocol):
    """Contract for code execution engines."""

    def execute(self, request: ExecutionRequest) -> ExecutionResult:
        """Execute the requested code and return its result."""
        ...
