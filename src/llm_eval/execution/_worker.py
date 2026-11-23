"""Standalone execution worker for the subprocess engine.

This module is intentionally self-contained: it imports only the Python
standard library and must never import ``llm_eval``. It is launched as a
script by the parent engine:

    [sys.executable, "-I", "-X", "utf8", _worker.py, request.json, result.json]

Communication happens exclusively through versioned JSON files. stdout and
stderr belong to the code under test and are never used for the protocol.

Known limitations (documented, not hidden):
- This is not a security sandbox.
- The stdout/stderr cap applies to writes through sys.stdout/sys.stderr.
  Direct descriptor writes (os.write) bypass the cap.
- The truncation marker is additional bytes beyond the 64 KB content cap.
"""

from __future__ import annotations

import json
import os
import sys
import threading
import time
import traceback
from collections.abc import Mapping
from typing import Any

PROTOCOL_VERSION = "1.0"

# Grace period for the losing main thread to wait until the timer has
# finished its write attempts. If the write remains stuck longer than this,
# the main thread exits with EXIT_WORKER_FAILURE. The parent's global timeout
# remains the ultimate backstop.
WRITE_GRACE_SECONDS = 5.0

# Exit codes are diagnostic only. The parent never classifies by exit code.
EXIT_OK = 0
EXIT_WORKER_FAILURE = 70

MAX_CAPTURE_BYTES = 64 * 1024
TRUNCATION_MARKER = "\n[truncated]"

_SERIALIZATION_FAILED = object()
_original_stdout: Any = None
_original_stderr: Any = None

_settle_lock = threading.Lock()
_claimed_by: str | None = None
_closed_phases: set[str] = set()
_write_finished = threading.Event()
_metrics: dict[str, float | None] = {
    "import_duration_ms": None,
    "call_duration_ms": None,
}
_result_path: str = ""


def _configure(result_path: str) -> None:
    """Reset all shared state for one execution run."""
    global _claimed_by, _closed_phases, _write_finished, _metrics, _result_path

    with _settle_lock:
        _claimed_by = None
        _closed_phases = set()
        _metrics = {
            "import_duration_ms": None,
            "call_duration_ms": None,
        }

    _write_finished = threading.Event()
    _result_path = result_path


def _terminate(code: int) -> None:
    """Flush captured output before terminating the worker process."""
    for stream in (_original_stdout, _original_stderr):
        if stream is not None:
            try:
                stream.flush()
            except BaseException:  # noqa: BLE001, S110
                pass

    os._exit(code)


def _atomic_write(result_path: str, payload: dict[str, Any]) -> None:
    """Write payload atomically: temporary file, fsync, then os.replace.

    This function is the test seam for deterministic race tests.
    """
    tmp_path = result_path + ".tmp"
    data = json.dumps(payload, allow_nan=False, ensure_ascii=False)

    with open(tmp_path, "w", encoding="utf-8") as handle:
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())

    os.replace(tmp_path, result_path)


def _write_fallback(original_exc: BaseException) -> None:
    """Attempt an infrastructure-error write after a failed primary write.

    Deliberately bypasses the claim check: only the claim owner calls this,
    after its own primary write failed.
    """
    try:
        _atomic_write(
            _result_path,
            _infrastructure_payload("ResultWriteError", original_exc),
        )
    except BaseException:  # noqa: BLE001, S110
        # If recovery also fails, the parent will detect the missing or
        # invalid result file and classify the failure.
        pass


def _attempt_write(payload: dict[str, Any]) -> bool:
    """Persist the result, falling back to an infrastructure error.

    Returns True only if the primary write succeeded. The event signals that
    all write attempts have finished, not that they succeeded.
    """
    try:
        _atomic_write(_result_path, payload)
        return True
    except BaseException as exc:  # noqa: BLE001
        _write_fallback(exc)
        return False
    finally:
        _write_finished.set()


def _close_phase(phase: str) -> None:
    """Close a phase so a late timeout callback cannot claim it."""
    with _settle_lock:
        _closed_phases.add(phase)


def _timer_owns() -> bool:
    with _settle_lock:
        return _claimed_by == "timer"


def _record_metric(name: str, value: float) -> None:
    with _settle_lock:
        _metrics[name] = value


def _yield_to_timer() -> None:
    """Wait for a winning timer to finish its write attempts.

    If the timer finishes, it has already fsync'd the result.
    Returning here allows the main thread to exit, which safely
    terminates the daemon timer thread.
    """
    finished = _write_finished.wait(timeout=WRITE_GRACE_SECONDS)
    if not finished:
        _terminate(EXIT_WORKER_FAILURE)


def _finish_main(payload: dict[str, Any]) -> None:
    """Claim the result for the main thread or yield to the timer."""
    global _claimed_by

    with _settle_lock:
        owner = _claimed_by is None
        if owner:
            _claimed_by = "main"

    if owner:
        ok = _attempt_write(payload)
        _terminate(EXIT_OK if ok else EXIT_WORKER_FAILURE)
    else:
        _yield_to_timer()


def _on_timeout(phase: str, seconds: float) -> None:
    """Timer callback. The first valid claimant determines the result."""
    global _claimed_by

    with _settle_lock:
        if phase in _closed_phases:
            return
        if _claimed_by is not None:
            return

        _claimed_by = "timer"
        metrics = dict(_metrics)

    payload = _base_payload("timeout")
    payload["timed_out_phase"] = phase
    payload["error"] = {
        "error_type": "TimeoutError",
        "message": f"Execution exceeded {phase} phase timeout",
        "details": {
            "phase": phase,
            "timeout_seconds": seconds,
        },
    }
    payload["metrics"] = metrics

    ok = _attempt_write(payload)
    _terminate(EXIT_OK if ok else EXIT_WORKER_FAILURE)


def _start_timer(
    phase: str,
    seconds: float | None,
) -> threading.Timer | None:
    if seconds is None:
        return None

    timer = threading.Timer(seconds, _on_timeout, args=(phase, seconds))
    timer.daemon = True
    timer.start()
    return timer


def _base_payload(outcome: str) -> dict[str, Any]:
    with _settle_lock:
        metrics = dict(_metrics)

    return {
        "protocol_version": PROTOCOL_VERSION,
        "outcome": outcome,
        "return_value": None,
        "args_after": None,
        "kwargs_after": None,
        "exception": None,
        "error": None,
        "timed_out_phase": None,
        "metrics": metrics,
    }


def _safe_str(value: BaseException) -> str:
    try:
        return str(value)
    except BaseException:  # noqa: BLE001
        return "<unprintable exception message>"


def _format_exc(exc: BaseException) -> str:
    return "".join(
        traceback.format_exception(
            type(exc),
            exc,
            exc.__traceback__,
        )
    )


def _exception_payload(exc: BaseException) -> dict[str, Any]:
    return {
        "exception_type": type(exc).__name__,
        "message": _safe_str(exc),
        "traceback": _format_exc(exc),
    }


def _import_error_payload(
    exc: BaseException | None,
    error_type: str,
    message: str,
) -> dict[str, Any]:
    payload = _base_payload("import_error")
    details: dict[str, Any] = {"phase": "import"}

    if exc is not None:
        details["traceback"] = _format_exc(exc)

    payload["error"] = {
        "error_type": error_type,
        "message": message,
        "details": details,
    }
    return payload


def _infrastructure_payload(
    error_type: str,
    exc: BaseException,
) -> dict[str, Any]:
    payload = _base_payload("infrastructure_error")
    payload["error"] = {
        "error_type": error_type,
        "message": _safe_str(exc),
        "details": {
            "traceback": _format_exc(exc),
        },
    }
    return payload


def _has_string_keys(value: Any) -> bool:
    """Check recursively that all mapping keys are strings."""
    if isinstance(value, Mapping):
        return all(
            isinstance(key, str) and _has_string_keys(item)
            for key, item in value.items()
        )

    if isinstance(value, (list, tuple)):
        return all(_has_string_keys(item) for item in value)

    return True


def _try_serialize(value: Any) -> Any:
    """Return the value if strictly JSON-serializable, else the sentinel.

    None is a valid result and never signals failure. Non-string mapping
    keys are rejected because json.dumps would silently coerce them.
    """
    try:
        if not _has_string_keys(value):
            return _SERIALIZATION_FAILED

        json.dumps(
            value,
            allow_nan=False,
            ensure_ascii=False,
        )
        return value
    except BaseException:  # noqa: BLE001
        return _SERIALIZATION_FAILED


class _CappedStream:
    """Cap Python-level writes to an underlying text stream.

    The limit counts UTF-8 bytes. Truncation occurs only at complete
    character boundaries. Writes through os.write on the raw descriptor
    bypass this cap by design. The truncation marker is appended once,
    beyond the content cap.
    """

    def __init__(self, underlying: Any, limit: int) -> None:
        self._underlying = underlying
        self._remaining = limit
        self._truncated = False

    def write(self, text: str) -> int:
        if not isinstance(text, str):
            raise TypeError("write() argument must be str")

        data = text.encode("utf-8", errors="replace")

        if len(data) <= self._remaining:
            self._remaining -= len(data)
            self._underlying.write(text)
            return len(text)

        accepted_text = ""
        if self._remaining > 0:
            candidate = data[: self._remaining]

            # Never split a multi-byte UTF-8 character. The loop removes
            # trailing bytes until the prefix is valid UTF-8.
            while candidate:
                try:
                    accepted_text = candidate.decode("utf-8")
                    break
                except UnicodeDecodeError:
                    candidate = candidate[:-1]

        if accepted_text:
            self._underlying.write(accepted_text)
            accepted_bytes = len(accepted_text.encode("utf-8"))
            self._remaining -= accepted_bytes

        self._mark_truncated()

        # Text streams report the number of characters accepted.
        return len(accepted_text)

    def _mark_truncated(self) -> None:
        if not self._truncated:
            self._truncated = True
            self._underlying.write(TRUNCATION_MARKER)

    def writelines(self, lines: Any) -> None:
        for line in lines:
            self.write(line)

    def flush(self) -> None:
        self._underlying.flush()

    def fileno(self) -> int:
        return self._underlying.fileno()

    def isatty(self) -> bool:
        return self._underlying.isatty()

    def __getattr__(self, name: str) -> Any:
        return getattr(self._underlying, name)


def _install_capture() -> None:
    global _original_stdout, _original_stderr

    _original_stdout = sys.stdout
    _original_stderr = sys.stderr

    sys.stdout = _CappedStream(_original_stdout, MAX_CAPTURE_BYTES)
    sys.stderr = _CappedStream(_original_stderr, MAX_CAPTURE_BYTES)


def _execute_request(request: dict[str, Any], result_path: str) -> None:
    _configure(result_path)

    try:
        _run_phases(request)
    except BaseException as exc:  # noqa: BLE001
        _finish_main(_infrastructure_payload("WorkerError", exc))


def _run_phases(request: dict[str, Any]) -> None:
    if request.get("protocol_version") != PROTOCOL_VERSION:
        _finish_main(
            _infrastructure_payload(
                "WorkerError",
                ValueError("Unsupported protocol_version in request"),
            )
        )
        return

    source_code = request["source_code"]
    entry_point = request["entry_point"]

    # Shallow copies preserve references to nested mutable values so that
    # mutations made by the function remain observable in args_after/kwargs_after.
    args = list(request.get("args", []))
    kwargs = dict(request.get("kwargs", {}))

    timeouts = request.get("phase_timeouts", {})

    namespace: dict[str, Any] = {}

    import_timer = _start_timer(
        "import",
        timeouts.get("import_seconds"),
    )
    started = time.perf_counter()

    try:
        exec(  # noqa: S102
            compile(source_code, "<model_code>", "exec"),
            namespace,
        )
    except BaseException as exc:  # noqa: BLE001
        elapsed = (time.perf_counter() - started) * 1000.0

        if import_timer is not None:
            import_timer.cancel()

        _close_phase("import")

        if _timer_owns():
            _yield_to_timer()
            return

        _record_metric("import_duration_ms", elapsed)
        _finish_main(
            _import_error_payload(
                exc,
                type(exc).__name__,
                _safe_str(exc),
            )
        )
        return

    elapsed = (time.perf_counter() - started) * 1000.0

    if import_timer is not None:
        import_timer.cancel()

    _close_phase("import")

    if _timer_owns():
        _yield_to_timer()
        return

    _record_metric("import_duration_ms", elapsed)

    if entry_point not in namespace:
        _finish_main(
            _import_error_payload(
                None,
                "EntryPointNotFoundError",
                f"entry_point '{entry_point}' not found in module namespace",
            )
        )
        return

    func = namespace[entry_point]

    if not callable(func):
        _finish_main(
            _import_error_payload(
                None,
                "EntryPointNotCallableError",
                f"entry_point '{entry_point}' is not callable",
            )
        )
        return

    call_timer = _start_timer(
        "call",
        timeouts.get("call_seconds"),
    )
    started = time.perf_counter()

    exc_payload: dict[str, Any] | None = None
    return_value: Any = None

    try:
        return_value = func(*args, **kwargs)
    except BaseException as exc:  # noqa: BLE001
        exc_payload = _exception_payload(exc)

    call_elapsed = (time.perf_counter() - started) * 1000.0

    if call_timer is not None:
        call_timer.cancel()

    _close_phase("call")

    if _timer_owns():
        _yield_to_timer()
        return

    _record_metric("call_duration_ms", call_elapsed)

    # Serialization priority is deterministic:
    # return_value -> args_after -> kwargs_after.
    # A function exception means there is no return value to serialize.
    serialized_return: Any = None
    failed_component: str | None = None

    if exc_payload is None:
        candidate = _try_serialize(return_value)
        if candidate is _SERIALIZATION_FAILED:
            failed_component = "return_value"
        else:
            serialized_return = candidate

    args_after = _try_serialize(args)
    kwargs_after = _try_serialize(kwargs)

    if failed_component is None and args_after is _SERIALIZATION_FAILED:
        failed_component = "args_after"

    if failed_component is None and kwargs_after is _SERIALIZATION_FAILED:
        failed_component = "kwargs_after"

    args_out = None if args_after is _SERIALIZATION_FAILED else args_after
    kwargs_out = None if kwargs_after is _SERIALIZATION_FAILED else kwargs_after

    if failed_component is not None:
        payload = _base_payload("serialization_error")

        details: dict[str, Any] = {
            "failed_component": failed_component,
            "original_outcome": ("exception" if exc_payload is not None else "success"),
        }

        if exc_payload is not None:
            details["original_exception_type"] = exc_payload["exception_type"]
            details["original_message"] = exc_payload["message"]

        payload["error"] = {
            "error_type": "SerializationError",
            "message": f"{failed_component} is not JSON-serializable",
            "details": details,
        }
        payload["return_value"] = serialized_return
        payload["args_after"] = args_out
        payload["kwargs_after"] = kwargs_out

        _finish_main(payload)
        return

    if exc_payload is not None:
        payload = _base_payload("exception")
        payload["exception"] = exc_payload
        payload["args_after"] = args_out
        payload["kwargs_after"] = kwargs_out

        _finish_main(payload)
        return

    payload = _base_payload("success")
    payload["return_value"] = serialized_return
    payload["args_after"] = args_out
    payload["kwargs_after"] = kwargs_out

    _finish_main(payload)


def main(argv: list[str] | None = None) -> None:
    args = sys.argv[1:] if argv is None else argv

    if len(args) != 2:
        sys.stderr.write("usage: _worker.py <request.json> <result.json>\n")
        _terminate(EXIT_WORKER_FAILURE)
        return

    request_path, result_path = args

    try:
        with open(request_path, encoding="utf-8") as handle:
            request = json.load(handle)
    except BaseException as exc:  # noqa: BLE001
        _configure(result_path)
        ok = _attempt_write(_infrastructure_payload("WorkerError", exc))
        _terminate(EXIT_OK if ok else EXIT_WORKER_FAILURE)
        return

    _install_capture()
    _execute_request(request, result_path)


if __name__ == "__main__":
    main()
