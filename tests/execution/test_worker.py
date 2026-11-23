"""Tests for the standalone execution worker.

The worker is loaded directly from its file path so that no llm_eval
package initialization is triggered. This preserves the standalone
contract: the worker must depend only on the standard library.
"""

from __future__ import annotations

import ast
import importlib.util
import json
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
WORKER_PATH = ROOT / "src" / "llm_eval" / "execution" / "_worker.py"


class _ExitCalled(Exception):
    def __init__(self, code: int) -> None:
        super().__init__(code)
        self.code = code


def _load_worker():
    spec = importlib.util.spec_from_file_location(
        "worker_under_test",
        WORKER_PATH,
    )
    assert spec is not None
    assert spec.loader is not None

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def worker():
    return _load_worker()


@pytest.fixture
def exits(monkeypatch, worker):
    recorded = []

    def fake_exit(code):
        recorded.append(code)
        raise _ExitCalled(code)

    monkeypatch.setattr(worker, "_terminate", fake_exit)
    return recorded


def _request(
    source,
    entry="f",
    args=(),
    kwargs=None,
    timeouts=None,
):
    return {
        "protocol_version": "1.0",
        "source_code": source,
        "entry_point": entry,
        "args": list(args),
        "kwargs": dict(kwargs or {}),
        "phase_timeouts": timeouts or {},
    }


def _run(worker, tmp_path, request):
    result_path = tmp_path / "result.json"
    worker._configure(str(result_path))

    try:
        worker._run_phases(request)
    except _ExitCalled:
        pass

    return json.loads(result_path.read_text(encoding="utf-8"))


def _spawn_raw(tmp_path, request_text, result_directory=None):
    request_path = tmp_path / "request.json"
    result_dir = tmp_path if result_directory is None else result_directory
    result_path = result_dir / "result.json"

    request_path.write_text(
        request_text,
        encoding="utf-8",
    )

    proc = subprocess.run(
        [
            sys.executable,
            "-I",
            "-X",
            "utf8",
            str(WORKER_PATH),
            str(request_path),
            str(result_path),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=20,
        check=False,
    )

    return proc, result_path


def _spawn(tmp_path, request):
    return _spawn_raw(
        tmp_path,
        json.dumps(request),
    )


class TestStandaloneContract:
    def test_worker_has_no_project_imports(self):
        tree = ast.parse(WORKER_PATH.read_text(encoding="utf-8"))

        imported_modules = []

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported_modules.extend(
                    alias.name.split(".")[0] for alias in node.names
                )
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported_modules.append(node.module.split(".")[0])

        assert "llm_eval" not in imported_modules

    def test_subprocess_does_not_load_llm_eval(self, tmp_path):
        source = (
            "import sys\n"
            "def f():\n"
            "    print(any(m.startswith('llm_eval') for m in sys.modules))\n"
        )

        proc, result_path = _spawn(tmp_path, _request(source))

        assert proc.returncode == 0
        assert proc.stdout.strip() == "False"
        assert (
            json.loads(result_path.read_text(encoding="utf-8"))["outcome"] == "success"
        )

    def test_worker_rejects_unsupported_protocol_version(
        self,
        worker,
        tmp_path,
        exits,
    ):
        request = _request("def f(): return 1")
        request["protocol_version"] = "2.0"

        data = _run(worker, tmp_path, request)

        assert data["outcome"] == "infrastructure_error"
        assert data["error"]["error_type"] == "WorkerError"

    def test_invalid_request_json(self, tmp_path):
        proc, result_path = _spawn_raw(
            tmp_path,
            "{invalid",
        )

        data = json.loads(result_path.read_text(encoding="utf-8"))

        assert proc.returncode == 0
        assert data["outcome"] == "infrastructure_error"
        assert data["error"]["error_type"] == "WorkerError"
        assert "JSONDecodeError" in data["error"]["details"]["traceback"]
        assert "traceback" in data["error"]["details"]

    def test_empty_request_json(self, tmp_path):
        proc, result_path = _spawn_raw(
            tmp_path,
            "",
        )

        data = json.loads(result_path.read_text(encoding="utf-8"))

        assert proc.returncode == 0
        assert data["outcome"] == "infrastructure_error"
        assert data["error"]["error_type"] == "WorkerError"
        assert "JSONDecodeError" in data["error"]["details"]["traceback"]
        assert "traceback" in data["error"]["details"]

    def test_missing_result_directory_exits_with_worker_failure(
        self,
        tmp_path,
    ):
        missing_directory = tmp_path / "missing-output"

        proc, result_path = _spawn_raw(
            tmp_path,
            json.dumps(_request("def f(): return 1")),
            result_directory=missing_directory,
        )

        temporary_path = Path(f"{result_path}.tmp")

        assert proc.returncode == 70
        assert not result_path.exists()
        assert not temporary_path.exists()


class TestSuccessAndNone:
    def test_success_with_value(self, worker, tmp_path, exits):
        data = _run(
            worker,
            tmp_path,
            _request("def f(): return 42"),
        )

        assert data["outcome"] == "success"
        assert data["return_value"] == 42
        assert data["exception"] is None
        assert data["error"] is None
        assert exits == [0]

    def test_none_return_is_success_not_failure(
        self,
        worker,
        tmp_path,
        exits,
    ):
        data = _run(
            worker,
            tmp_path,
            _request("def f(): return None"),
        )

        assert data["outcome"] == "success"
        assert data["return_value"] is None

    def test_metrics_are_recorded(self, worker, tmp_path, exits):
        data = _run(
            worker,
            tmp_path,
            _request("def f(): return 1"),
        )

        assert data["metrics"]["import_duration_ms"] >= 0
        assert data["metrics"]["call_duration_ms"] >= 0

    def test_result_contains_protocol_version(
        self,
        worker,
        tmp_path,
        exits,
    ):
        data = _run(
            worker,
            tmp_path,
            _request("def f(): return 1"),
        )

        assert data["protocol_version"] == "1.0"


class TestImportErrors:
    def test_syntax_error(self, worker, tmp_path, exits):
        data = _run(
            worker,
            tmp_path,
            _request("def f(:", entry="f"),
        )

        assert data["outcome"] == "import_error"
        assert data["error"]["error_type"] == "SyntaxError"
        assert "traceback" in data["error"]["details"]

    def test_missing_entry_point(self, worker, tmp_path, exits):
        data = _run(
            worker,
            tmp_path,
            _request("x = 1", entry="f"),
        )

        assert data["outcome"] == "import_error"
        assert data["error"]["error_type"] == "EntryPointNotFoundError"

    def test_entry_point_not_callable(self, worker, tmp_path, exits):
        data = _run(
            worker,
            tmp_path,
            _request("f = 42", entry="f"),
        )

        assert data["outcome"] == "import_error"
        assert data["error"]["error_type"] == "EntryPointNotCallableError"

    def test_module_level_raise_is_import_error(
        self,
        worker,
        tmp_path,
        exits,
    ):
        data = _run(
            worker,
            tmp_path,
            _request("raise RuntimeError('boom')"),
        )

        assert data["outcome"] == "import_error"
        assert data["error"]["error_type"] == "RuntimeError"

    def test_module_level_keyboard_interrupt_is_import_error(
        self,
        worker,
        tmp_path,
        exits,
    ):
        data = _run(
            worker,
            tmp_path,
            _request("raise KeyboardInterrupt('stop')"),
        )

        assert data["outcome"] == "import_error"
        assert data["error"]["error_type"] == "KeyboardInterrupt"


class TestFunctionExceptions:
    def test_value_error_is_exception(self, worker, tmp_path, exits):
        source = "def f():\n    raise ValueError('bad input')"

        data = _run(worker, tmp_path, _request(source))

        assert data["outcome"] == "exception"
        assert data["exception"]["exception_type"] == "ValueError"
        assert data["exception"]["message"] == "bad input"
        assert data["error"] is None

    def test_system_exit_is_exception_not_crash(
        self,
        worker,
        tmp_path,
        exits,
    ):
        source = "def f():\n    raise SystemExit(3)"

        data = _run(worker, tmp_path, _request(source))

        assert data["outcome"] == "exception"
        assert data["exception"]["exception_type"] == "SystemExit"

    def test_keyboard_interrupt_is_exception(
        self,
        worker,
        tmp_path,
        exits,
    ):
        source = "def f():\n    raise KeyboardInterrupt('stop')"

        data = _run(worker, tmp_path, _request(source))

        assert data["outcome"] == "exception"
        assert data["exception"]["exception_type"] == "KeyboardInterrupt"

    def test_memory_error_is_exception(self, worker, tmp_path, exits):
        source = "def f():\n    raise MemoryError()"

        data = _run(worker, tmp_path, _request(source))

        assert data["outcome"] == "exception"
        assert data["exception"]["exception_type"] == "MemoryError"


class TestTimeouts:
    def test_import_timeout(self, tmp_path):
        source = "while True:\n    pass"
        request = _request(
            source,
            timeouts={"import_seconds": 0.2},
        )

        proc, result_path = _spawn(tmp_path, request)
        data = json.loads(result_path.read_text(encoding="utf-8"))

        assert data["outcome"] == "timeout"
        assert data["timed_out_phase"] == "import"
        assert data["args_after"] is None
        assert proc.returncode == 0

    def test_call_timeout(self, tmp_path):
        source = "def f():\n    while True:\n        pass"
        request = _request(
            source,
            timeouts={"call_seconds": 0.2},
        )

        proc, result_path = _spawn(tmp_path, request)
        data = json.loads(result_path.read_text(encoding="utf-8"))

        assert data["outcome"] == "timeout"
        assert data["timed_out_phase"] == "call"
        assert data["args_after"] is None
        assert data["kwargs_after"] is None
        assert data["metrics"]["import_duration_ms"] is not None
        assert data["metrics"]["call_duration_ms"] is None
        assert proc.returncode == 0

    def test_args_after_is_null_on_timeout(self, tmp_path):
        source = "def f(xs):\n    xs.append(2)\n    while True:\n        pass"
        request = _request(
            source,
            args=([1],),
            timeouts={"call_seconds": 0.2},
        )

        proc, result_path = _spawn(tmp_path, request)
        data = json.loads(result_path.read_text(encoding="utf-8"))

        assert proc.returncode == 0
        assert data["outcome"] == "timeout"
        assert data["args_after"] is None
        assert data["kwargs_after"] is None


class TestSerialization:
    def test_nan_return_is_serialization_error(
        self,
        worker,
        tmp_path,
        exits,
    ):
        source = "def f():\n    return float('nan')"

        data = _run(worker, tmp_path, _request(source))

        assert data["outcome"] == "serialization_error"
        assert data["error"]["details"]["failed_component"] == "return_value"

    def test_infinity_return_is_serialization_error(
        self,
        worker,
        tmp_path,
        exits,
    ):
        source = "def f():\n    return float('inf')"

        data = _run(worker, tmp_path, _request(source))

        assert data["outcome"] == "serialization_error"
        assert data["error"]["details"]["failed_component"] == "return_value"

    def test_non_string_dict_keys_rejected(
        self,
        worker,
        tmp_path,
        exits,
    ):
        source = "def f():\n    return {1: 'a'}"

        data = _run(worker, tmp_path, _request(source))

        assert data["outcome"] == "serialization_error"
        assert data["error"]["details"]["failed_component"] == "return_value"

    def test_nested_non_string_dict_keys_rejected(
        self,
        worker,
        tmp_path,
        exits,
    ):
        source = "def f():\n    return {'outer': [{1: 'a'}]}"

        data = _run(worker, tmp_path, _request(source))

        assert data["outcome"] == "serialization_error"
        assert data["error"]["details"]["failed_component"] == "return_value"

    def test_sentinel_distinguishes_none_from_failure(self, worker):
        assert worker._try_serialize(None) is None
        assert worker._try_serialize(float("nan")) is worker._SERIALIZATION_FAILED

    def test_failed_component_precedence(self, worker, tmp_path, exits):
        source = "def f(xs):\n    xs.append(object())\n    return float('nan')"

        data = _run(
            worker,
            tmp_path,
            _request(source, args=([1],)),
        )

        assert data["outcome"] == "serialization_error"
        assert data["error"]["details"]["failed_component"] == "return_value"

    def test_return_and_kwargs_failure_prioritizes_return_value(
        self,
        worker,
        tmp_path,
        exits,
    ):
        source = (
            "def f(**kwargs):\n    kwargs['bad'] = object()\n    return float('nan')"
        )

        data = _run(
            worker,
            tmp_path,
            _request(source, kwargs={"value": 1}),
        )

        assert data["outcome"] == "serialization_error"
        assert data["error"]["details"]["failed_component"] == "return_value"

    def test_kwargs_after_serialization_failure(
        self,
        worker,
        tmp_path,
        exits,
    ):
        source = "def f(value):\n    value.append(object())\n    return 1"

        data = _run(
            worker,
            tmp_path,
            _request(
                source,
                kwargs={"value": []},
            ),
        )

        assert data["outcome"] == "serialization_error"
        assert data["error"]["details"]["failed_component"] == "kwargs_after"
        assert data["kwargs_after"] is None

    def test_args_after_failure_precedes_kwargs_after_failure(
        self,
        worker,
        tmp_path,
        exits,
    ):
        source = (
            "def f(xs, values):\n"
            "    xs.append(object())\n"
            "    values.append(object())\n"
            "    return 1"
        )

        data = _run(
            worker,
            tmp_path,
            _request(
                source,
                args=([1],),
                kwargs={"values": [1]},
            ),
        )

        assert data["outcome"] == "serialization_error"
        assert data["error"]["details"]["failed_component"] == "args_after"
        assert data["args_after"] is None
        assert data["kwargs_after"] is None


class TestMutationCapture:
    def test_mutation_visible_on_success(self, worker, tmp_path, exits):
        source = "def f(xs):\n    xs.append(100)\n    return len(xs)"

        data = _run(
            worker,
            tmp_path,
            _request(source, args=([1, 2],)),
        )

        assert data["outcome"] == "success"
        assert data["args_after"] == [[1, 2, 100]]

    def test_mutation_visible_on_exception(self, worker, tmp_path, exits):
        source = (
            "def f(xs):\n    xs.append(100)\n    raise ValueError('test exception')"
        )

        data = _run(
            worker,
            tmp_path,
            _request(source, args=([1],)),
        )

        assert data["outcome"] == "exception"
        assert data["args_after"] == [[1, 100]]

    def test_kwargs_mutation_visible_on_success(
        self,
        worker,
        tmp_path,
        exits,
    ):
        source = "def f(**kwargs):\n    kwargs['value'].append(2)\n    return True"

        data = _run(
            worker,
            tmp_path,
            _request(source, kwargs={"value": [1]}),
        )

        assert data["outcome"] == "success"
        assert data["kwargs_after"] == {"value": [1, 2]}

    def test_exception_plus_unserializable_mutation_conflict(
        self,
        worker,
        tmp_path,
        exits,
    ):
        source = (
            "def f(xs):\n"
            "    xs.append(object())\n"
            "    raise ValueError('test exception')"
        )

        data = _run(
            worker,
            tmp_path,
            _request(source, args=([1],)),
        )

        assert data["outcome"] == "serialization_error"

        details = data["error"]["details"]
        assert details["failed_component"] == "args_after"
        assert details["original_outcome"] == "exception"
        assert details["original_exception_type"] == "ValueError"
        assert details["original_message"] == "test exception"
        assert data["args_after"] is None


class TestAtomicWriteAndFallback:
    def test_write_failure_falls_back_to_infrastructure_error(
        self,
        worker,
        tmp_path,
        monkeypatch,
        exits,
    ):
        worker._configure(str(tmp_path / "result.json"))
        original = worker._atomic_write
        calls = []

        def flaky(path, payload):
            calls.append(payload["outcome"])
            if len(calls) == 1:
                raise OSError("disk full")
            original(path, payload)

        monkeypatch.setattr(worker, "_atomic_write", flaky)

        with pytest.raises(_ExitCalled):
            worker._finish_main(worker._base_payload("success"))

        data = json.loads((tmp_path / "result.json").read_text(encoding="utf-8"))

        assert data["outcome"] == "infrastructure_error"
        assert data["error"]["error_type"] == "ResultWriteError"
        assert exits == [70]
        assert worker._write_finished.is_set()

    def test_both_writes_fail_leave_no_result_file(
        self,
        worker,
        tmp_path,
        monkeypatch,
        exits,
    ):
        worker._configure(str(tmp_path / "result.json"))

        def always_fail(path, payload):
            raise OSError("disk full")

        monkeypatch.setattr(worker, "_atomic_write", always_fail)

        with pytest.raises(_ExitCalled):
            worker._finish_main(worker._base_payload("success"))

        assert not (tmp_path / "result.json").exists()
        assert worker._write_finished.is_set()
        assert exits == [70]

    def test_write_finished_set_even_on_failure(
        self,
        worker,
        tmp_path,
        monkeypatch,
        exits,
    ):
        worker._configure(str(tmp_path / "result.json"))

        def always_fail(path, payload):
            raise OSError("disk full")

        monkeypatch.setattr(worker, "_atomic_write", always_fail)

        with pytest.raises(_ExitCalled):
            worker._finish_main(worker._base_payload("success"))

        assert worker._write_finished.is_set()


class TestTimerRaces:
    def test_timer_wins_and_persists_before_main_returns(
        self,
        worker,
        tmp_path,
        monkeypatch,
    ):
        result_path = tmp_path / "result.json"
        worker._configure(str(result_path))

        original = worker._atomic_write
        started = threading.Event()
        release = threading.Event()
        order = []

        def slow_write(path, payload):
            started.set()
            assert release.wait(2)
            original(path, payload)
            order.append("write_done")

        monkeypatch.setattr(worker, "_atomic_write", slow_write)

        def fake_exit(code):
            order.append(f"exit:{code}")
            raise _ExitCalled(code)

        monkeypatch.setattr(worker, "_terminate", fake_exit)

        def timer_target():
            try:
                worker._on_timeout("call", 1.0)
            except _ExitCalled:
                pass

        timer_thread = threading.Thread(target=timer_target)
        timer_thread.start()

        assert started.wait(2)

        main_exits = []

        def main_target():
            try:
                worker._finish_main(worker._base_payload("success"))
            except _ExitCalled as exc:
                main_exits.append(exc.code)

        main_thread = threading.Thread(target=main_target)
        main_thread.start()

        time.sleep(0.1)
        assert main_exits == []
        assert not result_path.exists()

        release.set()
        timer_thread.join(2)
        main_thread.join(2)

        assert not timer_thread.is_alive()
        assert not main_thread.is_alive()

        data = json.loads(result_path.read_text(encoding="utf-8"))

        assert data["outcome"] == "timeout"
        assert main_exits == []
        assert order.index("write_done") < order.index("exit:0")

    def test_main_wins_late_timer_does_not_overwrite(
        self,
        worker,
        tmp_path,
        exits,
    ):
        worker._configure(str(tmp_path / "result.json"))
        worker._close_phase("call")

        worker._on_timeout("call", 1.0)

        with pytest.raises(_ExitCalled):
            worker._finish_main(worker._base_payload("success"))

        data = json.loads((tmp_path / "result.json").read_text(encoding="utf-8"))

        assert data["outcome"] == "success"
        assert worker._claimed_by == "main"

    def test_late_timer_after_phase_close_is_ignored(
        self,
        worker,
        tmp_path,
        exits,
    ):
        worker._configure(str(tmp_path / "result.json"))
        worker._close_phase("import")

        worker._on_timeout("import", 1.0)

        assert worker._claimed_by is None
        assert not (tmp_path / "result.json").exists()

    def test_import_timer_after_phase_close_is_ignored(
        self,
        worker,
        tmp_path,
        exits,
    ):
        worker._configure(str(tmp_path / "result.json"))

        worker._close_phase("import")
        worker._on_timeout("import", 0.01)

        assert worker._claimed_by is None
        assert not (tmp_path / "result.json").exists()

    def test_timer_write_failure_falls_back_to_infrastructure_error(
        self,
        worker,
        tmp_path,
        monkeypatch,
        exits,
    ):
        worker._configure(str(tmp_path / "result.json"))
        original = worker._atomic_write
        calls = []

        def flaky(path, payload):
            calls.append(payload["outcome"])
            if len(calls) == 1:
                raise OSError("disk full")
            original(path, payload)

        monkeypatch.setattr(worker, "_atomic_write", flaky)

        with pytest.raises(_ExitCalled) as exc_info:
            worker._on_timeout("call", 1.0)

        data = json.loads((tmp_path / "result.json").read_text(encoding="utf-8"))

        assert data["outcome"] == "infrastructure_error"
        assert data["error"]["error_type"] == "ResultWriteError"
        assert exc_info.value.code == 70
        assert worker._write_finished.is_set()

    def test_grace_period_exceeded_exits_worker_failure(
        self,
        worker,
        tmp_path,
        monkeypatch,
    ):
        worker._configure(str(tmp_path / "result.json"))
        worker._claimed_by = "timer"

        monkeypatch.setattr(
            worker,
            "WRITE_GRACE_SECONDS",
            0.05,
        )

        recorded = []

        def fake_exit(code):
            recorded.append(code)
            raise _ExitCalled(code)

        monkeypatch.setattr(worker, "_terminate", fake_exit)

        started = time.perf_counter()

        with pytest.raises(_ExitCalled):
            worker._yield_to_timer()

        elapsed = time.perf_counter() - started

        assert elapsed >= 0.05
        assert recorded == [70]
        assert not worker._write_finished.is_set()

    def test_grace_period_does_not_exit_if_timer_finished(
        self,
        worker,
        tmp_path,
        monkeypatch,
    ):
        worker._configure(str(tmp_path / "result.json"))
        worker._write_finished.set()

        recorded = []

        def fake_exit(code):
            recorded.append(code)
            raise _ExitCalled(code)

        monkeypatch.setattr(worker, "_terminate", fake_exit)

        worker._yield_to_timer()

        assert recorded == []


class TestStdoutStderrCapture:
    def test_exactly_64kb_has_no_marker(self, tmp_path):
        source = "import sys\ndef f():\n    sys.stdout.write('a' * 65536)\n"

        proc, _ = _spawn(tmp_path, _request(source))

        assert proc.stdout == "a" * 65536
        assert "[truncated]" not in proc.stdout

    def test_over_limit_appends_marker(self, tmp_path):
        source = "import sys\ndef f():\n    sys.stdout.write('a' * 65537)\n"

        proc, _ = _spawn(tmp_path, _request(source))

        assert proc.stdout == "a" * 65536 + "\n[truncated]"

    def test_unicode_capture(self, tmp_path):
        source = (
            "import sys\ndef f():\n    sys.stdout.write('\\u6d4b\\u8bd5' * 10000)\n"
        )

        proc, _ = _spawn(tmp_path, _request(source))

        assert proc.stdout == "\u6d4b\u8bd5" * 10000

    def test_unicode_truncation_does_not_split_character(
        self,
        tmp_path,
    ):
        source = "import sys\ndef f():\n    sys.stdout.write('a' * 65535 + '\\u6d4b')\n"

        proc, _ = _spawn(tmp_path, _request(source))

        assert proc.stdout == "a" * 65535 + "\n[truncated]"
        assert len(proc.stdout.encode("utf-8")) == (65535 + len(b"\n[truncated]"))

    def test_unicode_truncation_zero_chars_accepted(
        self,
        tmp_path,
    ):
        source = (
            "import sys\ndef f():\n    sys.stdout.write('a' * 65534 + '\\U0001f600')\n"
        )

        proc, _ = _spawn(tmp_path, _request(source))

        assert proc.stdout == "a" * 65534 + "\n[truncated]"
        assert len(proc.stdout.encode("utf-8")) == (65534 + len(b"\n[truncated]"))

    def test_os_write_bypasses_cap(self, tmp_path):
        source = "import os\ndef f():\n    os.write(1, b'x' * 70000)\n"

        proc, _ = _spawn(tmp_path, _request(source))

        assert len(proc.stdout) == 70000

    def test_stdout_and_stderr_capped_independently(self, tmp_path):
        source = (
            "import sys\n"
            "def f():\n"
            "    sys.stdout.write('a' * 70000)\n"
            "    sys.stderr.write('b' * 70000)\n"
        )

        proc, _ = _spawn(tmp_path, _request(source))

        assert proc.stdout == "a" * 65536 + "\n[truncated]"
        assert proc.stderr == "b" * 65536 + "\n[truncated]"
