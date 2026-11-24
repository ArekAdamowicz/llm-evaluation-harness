"""Subprocess-based execution engine."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import time
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from llm_eval.execution.models import (
    ExecutionMetrics,
    ExecutionOutcome,
    ExecutionRequest,
    ExecutionResult,
)
from llm_eval.results.models import ErrorInfo, ExceptionInfo

PROTOCOL_VERSION = "1.0"


def _thaw_json_value(value: Any) -> Any:
    """Convert immutable model containers into JSON-compatible values."""
    if isinstance(value, Mapping):
        return {key: _thaw_json_value(item) for key, item in value.items()}

    if isinstance(value, (tuple, list)):
        return [_thaw_json_value(item) for item in value]

    return value


def _decode_output(output: bytes | str | None) -> str:
    """Decode captured subprocess output.

    The worker already limits output and handles UTF-8 boundaries.
    This function only decodes the captured bytes.
    """
    if output is None:
        return ""
    if isinstance(output, str):
        return output
    return output.decode("utf-8", errors="replace")


def _error_info(payload: Any) -> ErrorInfo:
    """Convert a worker error payload into ErrorInfo."""
    if not isinstance(payload, dict):
        raise TypeError("Worker error payload must be an object")

    error_type = payload.get("error_type")
    message = payload.get("message")
    details = payload.get("details")

    if not isinstance(error_type, str):
        raise TypeError("Worker error_type must be a string")

    if not isinstance(message, str):
        raise TypeError("Worker error message must be a string")

    if details is not None and not isinstance(details, str):
        details = json.dumps(
            details,
            ensure_ascii=False,
            sort_keys=True,
        )

    return ErrorInfo(
        error_type=error_type,
        message=message,
        details=details,
    )


class SubprocessExecutionEngine:
    """Execute Python code in a separate worker process."""

    def execute(self, request: ExecutionRequest) -> ExecutionResult:
        """Execute a request and return its structured result."""
        config = request.config

        if config.sandbox_type != "subprocess":
            raise ValueError(
                "SubprocessExecutionEngine requires sandbox_type='subprocess'"
            )

        if config.memory_limit_mb is not None:
            raise ValueError(
                "SubprocessExecutionEngine does not support memory_limit_mb"
            )

        started = time.perf_counter()

        worker_path = Path(__file__).with_name("_worker.py").resolve()

        with tempfile.TemporaryDirectory(prefix="llm-eval-") as temp_dir:
            temp_path = Path(temp_dir)
            request_path = temp_path / "request.json"
            result_path = temp_path / "result.json"

            worker_request = {
                "protocol_version": PROTOCOL_VERSION,
                "source_code": request.source_code,
                "entry_point": request.entry_point,
                "args": _thaw_json_value(request.args),
                "kwargs": _thaw_json_value(request.kwargs),
                "phase_timeouts": {
                    "import_seconds": config.import_timeout_seconds,
                    "call_seconds": config.call_timeout_seconds,
                },
            }

            try:
                request_path.write_text(
                    json.dumps(
                        worker_request,
                        ensure_ascii=False,
                        allow_nan=False,
                    ),
                    encoding="utf-8",
                )

                completed = subprocess.run(
                    [
                        sys.executable,
                        "-I",
                        "-X",
                        "utf8",
                        str(worker_path),
                        str(request_path),
                        str(result_path),
                    ],
                    cwd=temp_path,
                    capture_output=True,
                    timeout=config.timeout_seconds,
                    check=False,
                )

            except subprocess.TimeoutExpired as exc:
                total_duration_ms = (time.perf_counter() - started) * 1000.0

                return ExecutionResult(
                    outcome=ExecutionOutcome.TIMEOUT,
                    metrics=ExecutionMetrics(
                        total_duration_ms=total_duration_ms,
                    ),
                    sandbox_type="subprocess",
                    error=ErrorInfo(
                        error_type="TimeoutError",
                        message=(
                            "Execution exceeded total timeout of "
                            f"{config.timeout_seconds} seconds"
                        ),
                    ),
                    timed_out_phase="total",
                    stdout=_decode_output(exc.stdout),
                    stderr=_decode_output(exc.stderr),
                )

            except (OSError, TypeError, ValueError) as exc:
                total_duration_ms = (time.perf_counter() - started) * 1000.0

                return ExecutionResult(
                    outcome=ExecutionOutcome.INFRASTRUCTURE_ERROR,
                    metrics=ExecutionMetrics(
                        total_duration_ms=total_duration_ms,
                    ),
                    sandbox_type="subprocess",
                    error=ErrorInfo(
                        error_type=type(exc).__name__,
                        message=str(exc),
                    ),
                )

            total_duration_ms = (time.perf_counter() - started) * 1000.0

            stdout = _decode_output(completed.stdout)
            stderr = _decode_output(completed.stderr)

            try:
                payload = json.loads(result_path.read_text(encoding="utf-8"))

                return self._build_result(
                    payload=payload,
                    total_duration_ms=total_duration_ms,
                    stdout=stdout,
                    stderr=stderr,
                    exit_code=completed.returncode,
                )

            except (
                OSError,
                json.JSONDecodeError,
                TypeError,
                ValueError,
                KeyError,
            ) as exc:
                return ExecutionResult(
                    outcome=ExecutionOutcome.INFRASTRUCTURE_ERROR,
                    metrics=ExecutionMetrics(
                        total_duration_ms=total_duration_ms,
                    ),
                    sandbox_type="subprocess",
                    error=ErrorInfo(
                        error_type="InvalidWorkerResult",
                        message=str(exc),
                    ),
                    stdout=stdout,
                    stderr=stderr,
                    exit_code=completed.returncode,
                )

    @staticmethod
    def _build_result(
        *,
        payload: Any,
        total_duration_ms: float,
        stdout: str,
        stderr: str,
        exit_code: int,
    ) -> ExecutionResult:
        """Validate and convert the worker response."""
        if not isinstance(payload, dict):
            raise TypeError("Worker result must be a JSON object")

        if payload.get("protocol_version") != PROTOCOL_VERSION:
            raise ValueError("Unsupported worker protocol version")

        try:
            outcome = ExecutionOutcome(payload["outcome"])
        except (KeyError, ValueError, TypeError) as exc:
            raise ValueError("Worker returned an unknown outcome") from exc

        worker_metrics = payload.get("metrics")
        if not isinstance(worker_metrics, dict):
            raise TypeError("Worker metrics must be an object")

        metrics = ExecutionMetrics(
            total_duration_ms=total_duration_ms,
            import_duration_ms=worker_metrics.get("import_duration_ms"),
            call_duration_ms=worker_metrics.get("call_duration_ms"),
        )

        exception = None
        if payload.get("exception") is not None:
            exception_payload = payload["exception"]
            if not isinstance(exception_payload, dict):
                raise TypeError("Worker exception payload must be an object")

            exception = ExceptionInfo(
                exception_type=exception_payload["exception_type"],
                message=exception_payload["message"],
                traceback=exception_payload.get("traceback"),
            )

        error = None
        if payload.get("error") is not None:
            error = _error_info(payload["error"])

        args_after_payload = payload.get("args_after")
        kwargs_after_payload = payload.get("kwargs_after")

        if args_after_payload is not None:
            if not isinstance(args_after_payload, list):
                raise TypeError("Worker args_after must be a JSON array")

            args_after = tuple(args_after_payload)
        else:
            args_after = None

        if kwargs_after_payload is not None:
            if not isinstance(kwargs_after_payload, dict):
                raise TypeError("Worker kwargs_after must be a JSON object")

            kwargs_after = kwargs_after_payload
        else:
            kwargs_after = None

        return ExecutionResult(
            outcome=outcome,
            metrics=metrics,
            sandbox_type="subprocess",
            return_value=payload.get("return_value"),
            args_after=args_after,
            kwargs_after=kwargs_after,
            exception=exception,
            error=error,
            timed_out_phase=payload.get("timed_out_phase"),
            stdout=stdout,
            stderr=stderr,
            exit_code=exit_code,
        )
