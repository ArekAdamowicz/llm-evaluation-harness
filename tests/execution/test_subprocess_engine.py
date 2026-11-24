"""Tests for the subprocess execution engine."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

import pytest

from llm_eval.execution.models import (
    ExecutionOutcome,
    ExecutionRequest,
)
from llm_eval.execution.subprocess_engine import SubprocessExecutionEngine
from llm_eval.experiments.config import ExecutionConfig


@pytest.fixture
def engine() -> SubprocessExecutionEngine:
    return SubprocessExecutionEngine()


def _request(
    source_code: str,
    *,
    entry_point: str = "f",
    args: tuple[Any, ...] = (),
    kwargs: dict[str, Any] | None = None,
    config: ExecutionConfig | None = None,
) -> ExecutionRequest:
    return ExecutionRequest(
        source_code=source_code,
        entry_point=entry_point,
        args=args,
        kwargs=kwargs if kwargs is not None else {},
        config=config if config is not None else ExecutionConfig(),
    )


class TestSuccessfulExecution:
    def test_returns_execution_result(
        self,
        engine: SubprocessExecutionEngine,
    ) -> None:
        result = engine.execute(_request("def f(): return 42"))

        assert result.outcome is ExecutionOutcome.SUCCESS
        assert result.return_value == 42
        assert result.exception is None
        assert result.error is None
        assert result.sandbox_type == "subprocess"
        assert result.timed_out_phase is None

    def test_none_return_is_success(
        self,
        engine: SubprocessExecutionEngine,
    ) -> None:
        result = engine.execute(_request("def f(): return None"))

        assert result.outcome is ExecutionOutcome.SUCCESS
        assert result.return_value is None

    def test_captures_argument_mutations(
        self,
        engine: SubprocessExecutionEngine,
    ) -> None:
        source = "def f(items):\n    items.append(3)\n    return len(items)\n"

        result = engine.execute(_request(source, args=([1, 2],)))

        assert result.outcome is ExecutionOutcome.SUCCESS
        assert result.return_value == 3
        assert result.args_after == ((1, 2, 3),)

    def test_captures_keyword_argument_mutations(
        self,
        engine: SubprocessExecutionEngine,
    ) -> None:
        source = "def f(items):\n    items.append(2)\n    return len(items)\n"

        result = engine.execute(_request(source, kwargs={"items": [1]}))

        assert result.outcome is ExecutionOutcome.SUCCESS
        assert result.return_value == 2
        assert result.kwargs_after == {"items": (1, 2)}

    def test_captures_stdout_and_stderr(
        self,
        engine: SubprocessExecutionEngine,
    ) -> None:
        source = (
            "import sys\n"
            "def f():\n"
            "    print('hello stdout')\n"
            "    print('hello stderr', file=sys.stderr)\n"
            "    return 1\n"
        )

        result = engine.execute(_request(source))

        assert result.outcome is ExecutionOutcome.SUCCESS
        assert "hello stdout" in result.stdout
        assert "hello stderr" in result.stderr

    def test_captures_unicode_output(
        self,
        engine: SubprocessExecutionEngine,
    ) -> None:
        source = "def f():\n    print('Zażółć gęślą jaźń')\n    return 1\n"

        result = engine.execute(_request(source))

        assert result.outcome is ExecutionOutcome.SUCCESS
        assert "Zażółć gęślą jaźń" in result.stdout

    def test_records_execution_metrics(
        self,
        engine: SubprocessExecutionEngine,
    ) -> None:
        result = engine.execute(_request("def f(): return 42"))

        assert result.metrics.total_duration_ms >= 0
        assert result.metrics.import_duration_ms is not None
        assert result.metrics.import_duration_ms >= 0
        assert result.metrics.call_duration_ms is not None
        assert result.metrics.call_duration_ms >= 0

    def test_records_worker_exit_code(
        self,
        engine: SubprocessExecutionEngine,
    ) -> None:
        result = engine.execute(_request("def f(): return 42"))

        assert result.exit_code == 0

    def test_preserves_truncation_marker_and_utf8_output(
        self,
        engine: SubprocessExecutionEngine,
    ) -> None:
        source = (
            "def f():\n"
            "    import sys\n"
            "    print('ą' * 40000)\n"
            "    print('ą' * 40000, file=sys.stderr)\n"
            "    return 1\n"
        )

        result = engine.execute(_request(source))

        assert result.outcome is ExecutionOutcome.SUCCESS

        assert result.stdout.count("\n[truncated]") == 1
        assert result.stderr.count("\n[truncated]") == 1

        assert "\ufffd" not in result.stdout
        assert "\ufffd" not in result.stderr

        assert result.stdout.endswith("\n[truncated]")
        assert result.stderr.endswith("\n[truncated]")


class TestExecutionFailures:
    def test_captures_function_exception(
        self,
        engine: SubprocessExecutionEngine,
    ) -> None:
        source = "def f():\n    raise ValueError('expected failure')\n"

        result = engine.execute(_request(source))

        assert result.outcome is ExecutionOutcome.EXCEPTION
        assert result.exception is not None
        assert result.exception.exception_type == "ValueError"
        assert result.exception.message == "expected failure"
        assert result.error is None

    def test_captures_import_error(
        self,
        engine: SubprocessExecutionEngine,
    ) -> None:
        source = "def f(:\n    pass\n"

        result = engine.execute(_request(source))

        assert result.outcome is ExecutionOutcome.IMPORT_ERROR
        assert result.error is not None
        assert result.exception is None

    def test_captures_serialization_error(
        self,
        engine: SubprocessExecutionEngine,
    ) -> None:
        source = "def f():\n    return object()\n"

        result = engine.execute(_request(source))

        assert result.outcome is ExecutionOutcome.SERIALIZATION_ERROR
        assert result.error is not None
        assert result.exception is None

    def test_enforces_total_timeout(
        self,
        engine: SubprocessExecutionEngine,
    ) -> None:
        source = "def f():\n    while True:\n        pass\n"

        config = ExecutionConfig(timeout_seconds=0.5)

        result = engine.execute(_request(source, config=config))

        assert result.outcome is ExecutionOutcome.TIMEOUT
        assert result.timed_out_phase == "total"
        assert result.error is not None
        assert result.exception is None

        config = ExecutionConfig(timeout_seconds=0.5)

    def test_enforces_call_timeout(
        self,
        engine: SubprocessExecutionEngine,
    ) -> None:
        source = "def f():\n    while True:\n        pass\n"

        config = ExecutionConfig(
            timeout_seconds=5.0,
            call_timeout_seconds=0.5,
        )

        result = engine.execute(_request(source, config=config))

        assert result.outcome is ExecutionOutcome.TIMEOUT
        assert result.timed_out_phase == "call"
        assert result.error is not None
        assert result.exception is None

    def test_enforces_import_timeout(
        self,
        engine: SubprocessExecutionEngine,
    ) -> None:
        source = "while True:\n    pass\n\ndef f():\n    return 1\n"

        config = ExecutionConfig(
            timeout_seconds=5.0,
            import_timeout_seconds=0.5,
        )

        result = engine.execute(_request(source, config=config))

        assert result.outcome is ExecutionOutcome.TIMEOUT
        assert result.timed_out_phase == "import"
        assert result.error is not None
        assert result.exception is None


class TestApiBoundaries:
    def test_rejects_non_subprocess_sandbox(
        self,
        engine: SubprocessExecutionEngine,
    ) -> None:
        config = ExecutionConfig(sandbox_type="docker")

        with pytest.raises(ValueError, match="sandbox_type"):
            engine.execute(_request("def f(): return 1", config=config))

    def test_rejects_memory_limit(
        self,
        engine: SubprocessExecutionEngine,
    ) -> None:
        config = ExecutionConfig(memory_limit_mb=128)

        with pytest.raises(ValueError, match="memory_limit_mb"):
            engine.execute(_request("def f(): return 1", config=config))


class TestWorkerProtocol:
    def test_handles_malformed_worker_result(
        self,
        engine: SubprocessExecutionEngine,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        def fake_run(command: list[str], **kwargs: Any) -> subprocess.CompletedProcess:
            result_path = Path(command[-1])
            result_path.write_text("{ invalid json", encoding="utf-8")

            return subprocess.CompletedProcess(
                args=command,
                returncode=0,
                stdout=b"",
                stderr=b"",
            )

        monkeypatch.setattr(
            "llm_eval.execution.subprocess_engine.subprocess.run",
            fake_run,
        )

        result = engine.execute(_request("def f():\n    return 1\n"))

        assert result.outcome is ExecutionOutcome.INFRASTRUCTURE_ERROR
        assert result.error is not None
        assert result.error.error_type == "InvalidWorkerResult"
        assert result.exit_code == 0

    def test_handles_worker_result_with_missing_required_fields(
        self,
        engine: SubprocessExecutionEngine,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        def fake_run(command: list[str], **kwargs: Any) -> subprocess.CompletedProcess:
            result_path = Path(command[-1])
            result_path.write_text(
                """
                {
                    "protocol_version": "1.0",
                    "outcome": "success",
                    "return_value": 42,
                    "args_after": [],
                    "kwargs_after": {},
                    "exception": null,
                    "error": null,
                    "timed_out_phase": null
                }
                """,
                encoding="utf-8",
            )

            return subprocess.CompletedProcess(
                args=command,
                returncode=0,
                stdout=b"",
                stderr=b"",
            )

        monkeypatch.setattr(
            "llm_eval.execution.subprocess_engine.subprocess.run",
            fake_run,
        )

        result = engine.execute(_request("def f():\n    return 1\n"))

        assert result.outcome is ExecutionOutcome.INFRASTRUCTURE_ERROR
        assert result.error is not None
        assert result.error.error_type == "InvalidWorkerResult"
        assert result.exit_code == 0

    def test_accepts_valid_result_with_nonzero_exit_code(
        self,
        engine: SubprocessExecutionEngine,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        def fake_run(command: list[str], **kwargs: Any) -> subprocess.CompletedProcess:
            result_path = Path(command[-1])
            result_path.write_text(
                """
                {
                    "protocol_version": "1.0",
                    "outcome": "success",
                    "return_value": 42,
                    "args_after": [],
                    "kwargs_after": {},
                    "exception": null,
                    "error": null,
                    "timed_out_phase": null,
                    "metrics": {
                        "import_duration_ms": 1.0,
                        "call_duration_ms": 2.0
                    }
                }
                """,
                encoding="utf-8",
            )

            return subprocess.CompletedProcess(
                args=command,
                returncode=70,
                stdout=b"",
                stderr=b"worker exited after writing result",
            )

        monkeypatch.setattr(
            "llm_eval.execution.subprocess_engine.subprocess.run",
            fake_run,
        )

        result = engine.execute(_request("def f():\n    return 1\n"))

        assert result.outcome is ExecutionOutcome.SUCCESS
        assert result.return_value == 42

        assert result.exit_code == 70

    def test_handles_missing_worker_result(
        self,
        engine: SubprocessExecutionEngine,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        def fake_run(command: list[str], **kwargs: Any) -> subprocess.CompletedProcess:
            return subprocess.CompletedProcess(
                args=command,
                returncode=0,
                stdout=b"",
                stderr=b"",
            )

        monkeypatch.setattr(
            "llm_eval.execution.subprocess_engine.subprocess.run",
            fake_run,
        )

        result = engine.execute(_request("def f():\n    return 1\n"))

        assert result.outcome is ExecutionOutcome.INFRASTRUCTURE_ERROR
        assert result.error is not None
        assert result.error.error_type == "InvalidWorkerResult"
        assert result.exit_code == 0

    def test_rejects_unsupported_protocol_version(
        self,
        engine: SubprocessExecutionEngine,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        def fake_run(command: list[str], **kwargs: Any) -> subprocess.CompletedProcess:
            result_path = Path(command[-1])
            result_path.write_text(
                """
                {
                    "protocol_version": "99.0",
                    "outcome": "success",
                    "return_value": 42,
                    "args_after": [],
                    "kwargs_after": {},
                    "exception": null,
                    "error": null,
                    "timed_out_phase": null,
                    "metrics": {
                        "import_duration_ms": 1.0,
                        "call_duration_ms": 2.0
                    }
                }
                """,
                encoding="utf-8",
            )

            return subprocess.CompletedProcess(
                args=command,
                returncode=0,
                stdout=b"",
                stderr=b"",
            )

        monkeypatch.setattr(
            "llm_eval.execution.subprocess_engine.subprocess.run",
            fake_run,
        )

        result = engine.execute(_request("def f():\n    return 1\n"))

        assert result.outcome is ExecutionOutcome.INFRASTRUCTURE_ERROR
        assert result.error is not None
        assert result.error.error_type == "InvalidWorkerResult"
        assert "protocol version" in result.error.message.lower()
