"""Tests for llm_eval.results.storage."""

import json
import re
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, patch

import pytest

from llm_eval.results import storage
from llm_eval.results.models import (
    ErrorInfo,
    EvaluationRun,
    Metrics,
    TestResult,
    TestStatus,
)
from llm_eval.results.storage import (
    RESULTS_SCHEMA_VERSION,
    _validate_path_segment,
    build_run_document,
    save_run,
)


class TestBuildRunDocument:
    def test_empty_results(self):
        """Document with no results."""
        run = EvaluationRun(
            dataset_id="CG-001",
            dataset_version="1.0",
            task_version="1.2",
        )
        doc = build_run_document(run, [])

        assert doc["schema_version"] == RESULTS_SCHEMA_VERSION
        assert doc["run"]["run_id"] == run.run_id
        assert doc["summary"]["total"] == 0
        assert doc["summary"]["PASS"] == 0
        assert doc["results"] == []

    def test_single_pass_result(self):
        """Document with one PASS result."""
        run = EvaluationRun(
            dataset_id="CG-001",
            dataset_version="1.0",
            task_version="1.2",
        )
        result = TestResult(
            run_id=run.run_id,
            test_case_id="CG-001-F01",
            status=TestStatus.PASS,
            actual_result=2.5,
        )
        doc = build_run_document(run, [result])

        assert doc["summary"]["total"] == 1
        assert doc["summary"]["PASS"] == 1
        assert doc["summary"]["FAIL"] == 0
        assert len(doc["results"]) == 1
        assert doc["results"][0]["test_case_id"] == "CG-001-F01"
        assert doc["results"][0]["status"] == "PASS"

    def test_mixed_statuses(self):
        """Document with mixed PASS/FAIL/ERROR."""
        run = EvaluationRun(dataset_id="CG-001")

        results = [
            TestResult(run_id=run.run_id, status=TestStatus.PASS),
            TestResult(run_id=run.run_id, status=TestStatus.PASS),
            TestResult(run_id=run.run_id, status=TestStatus.FAIL),
            TestResult(
                run_id=run.run_id,
                status=TestStatus.ERROR,
                error=ErrorInfo(error_type="TestError", message="test error"),
            ),
            TestResult(run_id=run.run_id, status=TestStatus.SKIPPED),
        ]

        doc = build_run_document(run, results)

        assert doc["summary"]["total"] == 5
        assert doc["summary"]["PASS"] == 2
        assert doc["summary"]["FAIL"] == 1
        assert doc["summary"]["ERROR"] == 1
        assert doc["summary"]["SKIPPED"] == 1

    def test_run_id_mismatch_raises(self):
        """Results with different run_id should raise ValueError."""
        run = EvaluationRun(dataset_id="CG-001")
        result = TestResult(run_id="different-run-id", status=TestStatus.PASS)

        with pytest.raises(ValueError, match="has run_id"):
            build_run_document(run, [result])

    def test_json_serializable(self):
        """Document should be JSON-serializable with allow_nan=False."""
        run = EvaluationRun(dataset_id="CG-001")
        result = TestResult(
            run_id=run.run_id,
            status=TestStatus.PASS,
            actual_result=2.5,
            metrics=Metrics(latency_ms=100.5, input_tokens=50),
        )
        doc = build_run_document(run, [result])

        json_str = json.dumps(doc, allow_nan=False)
        assert json_str is not None

        loaded = json.loads(json_str)
        assert loaded["schema_version"] == RESULTS_SCHEMA_VERSION

    def test_preserves_result_order(self):
        """Results should maintain their order in the document."""
        run = EvaluationRun(dataset_id="CG-001")
        results = [
            TestResult(run_id=run.run_id, test_case_id="F01", status=TestStatus.PASS),
            TestResult(run_id=run.run_id, test_case_id="F02", status=TestStatus.FAIL),
            TestResult(run_id=run.run_id, test_case_id="F03", status=TestStatus.PASS),
        ]

        doc = build_run_document(run, results)

        assert doc["results"][0]["test_case_id"] == "F01"
        assert doc["results"][1]["test_case_id"] == "F02"
        assert doc["results"][2]["test_case_id"] == "F03"


class TestSaveRun:
    def test_save_creates_file(self, tmp_path):
        """save_run creates JSON file in correct location."""
        run = EvaluationRun(
            dataset_id="CG-001",
            dataset_version="1.0",
            task_version="1.2",
        )
        result = TestResult(
            run_id=run.run_id,
            test_case_id="CG-001-F01",
            status=TestStatus.PASS,
        )

        saved_path = save_run(run, [result], tmp_path)

        assert saved_path.exists()
        assert saved_path.parent == tmp_path / "CG-001"
        assert saved_path.name.startswith(
            f"run_{run.started_at.strftime('%Y-%m-%d')}_{run.run_id}"
        )
        assert saved_path.suffix == ".json"

    def test_save_with_task_category(self, tmp_path):
        """save_run creates nested directory structure with task_category."""
        run = EvaluationRun(
            dataset_id="CG-001",
            dataset_version="1.0",
            task_version="1.2",
        )
        result = TestResult(
            run_id=run.run_id,
            test_case_id="CG-001-F01",
            status=TestStatus.PASS,
        )

        saved_path = save_run(run, [result], tmp_path, task_category="code-generation")

        assert saved_path.exists()
        assert saved_path.parent == tmp_path / "code-generation" / "CG-001"

    def test_save_creates_directories(self, tmp_path):
        """save_run creates nested directories if needed."""
        run = EvaluationRun(dataset_id="CG-001")
        result = TestResult(run_id=run.run_id, status=TestStatus.PASS)

        results_root = tmp_path / "results"
        saved_path = save_run(run, [result], results_root)

        assert saved_path.exists()
        assert saved_path.parent == results_root / "CG-001"

    def test_save_valid_json(self, tmp_path):
        """Saved file contains valid JSON."""
        run = EvaluationRun(dataset_id="CG-001")
        result = TestResult(
            run_id=run.run_id,
            status=TestStatus.PASS,
            actual_result=2.5,
        )

        saved_path = save_run(run, [result], tmp_path)

        with open(saved_path, encoding="utf-8") as f:
            data = json.load(f)

        assert data["schema_version"] == RESULTS_SCHEMA_VERSION
        assert data["summary"]["total"] == 1
        assert data["summary"]["PASS"] == 1

    def test_save_empty_results(self, tmp_path):
        """save_run handles empty results list."""
        run = EvaluationRun(dataset_id="CG-001")

        saved_path = save_run(run, [], tmp_path)

        assert saved_path.exists()

        with open(saved_path, encoding="utf-8") as f:
            data = json.load(f)

        assert data["summary"]["total"] == 0
        assert data["results"] == []

    def test_save_run_id_mismatch_raises(self, tmp_path):
        """save_run raises if result has different run_id."""
        run = EvaluationRun(dataset_id="CG-001")
        result = TestResult(run_id="wrong-id", status=TestStatus.PASS)

        with pytest.raises(ValueError, match="has run_id"):
            save_run(run, [result], tmp_path)

    def test_save_date_from_started_at(self, tmp_path):
        """Filename uses date from started_at, not current time."""
        yesterday = datetime.now(timezone.utc) - timedelta(days=1)
        run = EvaluationRun(
            dataset_id="CG-001",
            started_at=yesterday,
        )
        result = TestResult(run_id=run.run_id, status=TestStatus.PASS)

        saved_path = save_run(run, [result], tmp_path)

        expected_date = yesterday.strftime("%Y-%m-%d")
        assert expected_date in saved_path.name

    def test_save_utf8_encoding(self, tmp_path):
        """Saved file uses UTF-8 encoding."""
        run = EvaluationRun(dataset_id="CG-001")
        result = TestResult(
            run_id=run.run_id,
            status=TestStatus.PASS,
            metadata={"note": "测试"},
        )

        saved_path = save_run(run, [result], tmp_path)

        with open(saved_path, encoding="utf-8") as f:
            content = f.read()

        assert "测试" in content

    def test_save_no_temp_file_on_success(self, tmp_path):
        """No temporary files remain after successful save."""
        run = EvaluationRun(dataset_id="CG-001")
        result = TestResult(run_id=run.run_id, status=TestStatus.PASS)

        saved_path = save_run(run, [result], tmp_path)

        temp_files = list(saved_path.parent.glob(".tmp_*"))
        assert len(temp_files) == 0

    def test_save_overwrites_existing(self, tmp_path):
        """save_run can overwrite existing file with same name."""
        run = EvaluationRun(dataset_id="CG-001")
        result1 = TestResult(
            run_id=run.run_id, status=TestStatus.PASS, actual_result=1.0
        )
        result2 = TestResult(
            run_id=run.run_id, status=TestStatus.PASS, actual_result=2.0
        )

        path1 = save_run(run, [result1], tmp_path)
        path2 = save_run(run, [result2], tmp_path)

        assert path1 == path2

        with open(path2, encoding="utf-8") as f:
            data = json.load(f)

        assert data["results"][0]["actual_result"] == 2.0

    def test_special_float_serialization(self, tmp_path):
        """NaN and Infinity are saved as tagged objects, not invalid JSON."""
        run = EvaluationRun(dataset_id="CG-001")
        result = TestResult(
            run_id=run.run_id,
            status=TestStatus.PASS,
            input_data={"values": [1.0, float("nan"), float("inf"), float("-inf")]},
        )

        saved_path = save_run(run, [result], tmp_path)

        with open(saved_path, encoding="utf-8") as f:
            data = json.load(f)

        values = data["results"][0]["input_data"]["values"]
        assert values[0] == 1.0
        assert values[1] == {"$type": "float", "value": "nan"}
        assert values[2] == {"$type": "float", "value": "inf"}
        assert values[3] == {"$type": "float", "value": "-inf"}

    def test_large_integer_preservation(self, tmp_path):
        """Large integers preserve all digits."""
        run = EvaluationRun(dataset_id="CG-001")
        large_int = 10**400
        result = TestResult(
            run_id=run.run_id,
            status=TestStatus.PASS,
            input_data={"numbers": [large_int, -large_int]},
        )

        saved_path = save_run(run, [result], tmp_path)

        with open(saved_path, encoding="utf-8") as f:
            content = f.read()

        assert str(large_int) in content
        assert str(-large_int) in content

        data = json.loads(content)
        numbers = data["results"][0]["input_data"]["numbers"]
        assert numbers[0] == large_int
        assert numbers[1] == -large_int

    def test_atomic_write_cleanup_on_failure(self, tmp_path):
        """No temporary files remain after os.replace() failure."""
        run = EvaluationRun(dataset_id="CG-001")
        result = TestResult(run_id=run.run_id, status=TestStatus.PASS)

        with (
            patch(
                "llm_eval.results.storage.os.replace",
                side_effect=OSError("Mock error"),
            ),
            pytest.raises(OSError, match="Mock error"),
        ):
            save_run(run, [result], tmp_path)

        temp_files = list((tmp_path / "CG-001").glob(".tmp_*"))
        assert len(temp_files) == 0

    def test_invalid_task_category_empty(self, tmp_path):
        """Empty task_category raises ValueError."""
        run = EvaluationRun(dataset_id="CG-001")
        result = TestResult(run_id=run.run_id, status=TestStatus.PASS)

        with pytest.raises(ValueError, match="cannot be empty"):
            save_run(run, [result], tmp_path, task_category="")

    def test_invalid_task_category_path_separator(self, tmp_path):
        """task_category with path separators raises ValueError."""
        run = EvaluationRun(dataset_id="CG-001")
        result = TestResult(run_id=run.run_id, status=TestStatus.PASS)

        with pytest.raises(ValueError, match="contains path separator"):
            save_run(run, [result], tmp_path, task_category="code/generation")

    def test_invalid_task_category_parent_directory(self, tmp_path):
        """task_category as '.' or '..' raises ValueError."""
        run = EvaluationRun(dataset_id="CG-001")
        result = TestResult(run_id=run.run_id, status=TestStatus.PASS)

        with pytest.raises(ValueError, match="cannot be '.' or '..'"):
            save_run(run, [result], tmp_path, task_category="..")

    def test_date_converted_to_utc(self, tmp_path):
        """Date in filename is converted to UTC regardless of timezone."""
        tz_minus_5 = timezone(timedelta(hours=-5))
        local_time = datetime(2026, 11, 20, 23, 0, 0, tzinfo=tz_minus_5)

        run = EvaluationRun(
            dataset_id="CG-001",
            started_at=local_time,
        )
        result = TestResult(run_id=run.run_id, status=TestStatus.PASS)

        saved_path = save_run(run, [result], tmp_path)

        assert "2026-11-21" in saved_path.name

    # Path validation integration tests

    def test_invalid_dataset_id_path_traversal(self, tmp_path):
        """dataset_id must not allow saving outside the results root."""
        root = tmp_path / "results"
        run = EvaluationRun(dataset_id="../outside")

        with pytest.raises(ValueError, match="dataset_id"):
            save_run(run, [], root)

        assert not (tmp_path / "outside").exists()
        assert not root.exists()

    def test_invalid_run_id_path_traversal(self, tmp_path):
        """run_id must not allow saving outside the dataset directory."""
        root = tmp_path / "results"
        run = EvaluationRun(
            dataset_id="CG-001",
            run_id="../../../outside",
        )

        dataset_dir = root / "CG-001"
        date = run.started_at.astimezone(timezone.utc).strftime("%Y-%m-%d")

        # Prepare the intermediate directory required to demonstrate
        # that the unvalidated filename could traverse outside dataset_dir.
        (dataset_dir / f"run_{date}_..").mkdir(parents=True)

        with pytest.raises(ValueError, match="run_id"):
            save_run(run, [], root)

        assert not (root / "outside.json").exists()

    def test_invalid_dataset_id_rejected_before_document_build(
        self, tmp_path, monkeypatch
    ):
        """Invalid dataset_id must be rejected before building the document."""
        build_spy = Mock(wraps=storage.build_run_document)
        monkeypatch.setattr(storage, "build_run_document", build_spy)

        run = EvaluationRun(dataset_id="../outside")

        with pytest.raises(ValueError, match="dataset_id"):
            save_run(run, [], tmp_path / "results")

        build_spy.assert_not_called()

    def test_invalid_dataset_id_rejected_before_json_serialization(
        self, tmp_path, monkeypatch
    ):
        """Invalid dataset_id must be rejected before JSON serialization."""
        dumps_spy = Mock(wraps=json.dumps)
        monkeypatch.setattr(storage.json, "dumps", dumps_spy)

        run = EvaluationRun(dataset_id="../outside")
        result = TestResult(run_id=run.run_id, status=TestStatus.PASS)

        with pytest.raises(ValueError, match="dataset_id"):
            save_run(run, [result], tmp_path / "results")

        dumps_spy.assert_not_called()

    def test_invalid_dataset_id_validated_before_result_run_id_mismatch(self, tmp_path):
        """Path segment validation takes precedence over result consistency."""
        run = EvaluationRun(dataset_id="../outside")
        result = TestResult(run_id="wrong-run-id", status=TestStatus.PASS)

        with pytest.raises(ValueError, match="dataset_id"):
            save_run(run, [result], tmp_path)

    def test_invalid_task_category_rejected_before_json_serialization(
        self, tmp_path, monkeypatch
    ):
        """Invalid task_category must be rejected before JSON serialization."""
        dumps_spy = Mock(wraps=json.dumps)
        monkeypatch.setattr(storage.json, "dumps", dumps_spy)

        run = EvaluationRun(dataset_id="CG-001")
        result = TestResult(run_id=run.run_id, status=TestStatus.PASS)

        with pytest.raises(ValueError, match="task_category"):
            save_run(
                run,
                [result],
                tmp_path / "results",
                task_category="../invalid",
            )

        dumps_spy.assert_not_called()


class TestValidatePathSegment:
    """Unit tests for _validate_path_segment helper."""

    @pytest.mark.parametrize(
        "value,field_name",
        [
            ("dataset", "dataset_id"),
            ("CG-001", "dataset_id"),
            ("run_123", "run_id"),
            ("v1.2.3", "dataset_id"),
            ("my dataset", "dataset_id"),
            ("zbiór_danych", "dataset_id"),
            ("test.case.with.dots", "dataset_id"),
            ("dataset.v1", "dataset_id"),
            ("a" * 200, "task_category"),
            ("a" * 200, "dataset_id"),
            ("a" * 150, "run_id"),
            ("ą" * 100, "task_category"),
            ("ą" * 100, "dataset_id"),
            ("ą" * 75, "run_id"),
        ],
    )
    def test_accepts_valid_values(self, value, field_name):
        """Valid values should be returned unchanged."""
        result = _validate_path_segment(value, field_name)

        assert result == value

    @pytest.mark.parametrize(
        "value",
        [
            "CON",
            "PRN",
            "AUX",
            "NUL",
            "COM1",
            "COM9",
            "LPT1",
            "LPT9",
        ],
    )
    def test_accepts_windows_reserved_names(self, value):
        """Windows reserved names are not rejected by this helper."""
        assert _validate_path_segment(value, "dataset_id") == value

    @pytest.mark.parametrize(
        "value,field_name,expected_message",
        [
            # Invalid types
            (None, "dataset_id", "must be a string"),
            (123, "dataset_id", "must be a string"),
            ([], "dataset_id", "must be a string"),
            # Empty and whitespace-only values
            ("", "dataset_id", "cannot be empty"),
            (" ", "dataset_id", "cannot have leading or trailing whitespace"),
            (" test", "dataset_id", "cannot have leading or trailing whitespace"),
            ("test ", "dataset_id", "cannot have leading or trailing whitespace"),
            ("\ttest", "dataset_id", "cannot have leading or trailing whitespace"),
            # Dot-only path segments
            (".", "dataset_id", "cannot be '.' or '..'"),
            ("..", "dataset_id", "cannot be '.' or '..'"),
            # Path separators
            ("../outside", "dataset_id", "contains path separator"),
            ("foo/bar", "dataset_id", "contains path separator"),
            ("foo\\bar", "dataset_id", "contains path separator"),
            # Control characters
            ("\x00", "dataset_id", "contains control characters"),
            ("foo\nbar", "dataset_id", "contains control characters"),
            ("foo\rbar", "dataset_id", "contains control characters"),
            ("foo\x85bar", "dataset_id", "contains control characters"),
            # Characters forbidden on Windows
            ("foo<bar", "dataset_id", "contains characters not allowed on Windows"),
            ("foo>bar", "dataset_id", "contains characters not allowed on Windows"),
            ("foo:bar", "dataset_id", "contains characters not allowed on Windows"),
            ('foo"bar', "dataset_id", "contains characters not allowed on Windows"),
            ("foo|bar", "dataset_id", "contains characters not allowed on Windows"),
            ("foo?bar", "dataset_id", "contains characters not allowed on Windows"),
            ("foo*bar", "dataset_id", "contains characters not allowed on Windows"),
            # Trailing dot
            ("dataset.", "dataset_id", "cannot end with a dot"),
            # Invalid Unicode: lone surrogate cannot be encoded as UTF-8
            ("\ud800", "dataset_id", "contains invalid Unicode"),
        ],
    )
    def test_rejects_invalid_values(self, value, field_name, expected_message):
        """Invalid values should raise ValueError with a useful message."""
        with pytest.raises(ValueError, match=re.escape(expected_message)):
            _validate_path_segment(value, field_name)

    def test_rejects_unknown_field_name(self):
        """Unknown field names should raise an explicit ValueError."""
        with pytest.raises(ValueError, match="Unknown field name"):
            _validate_path_segment("valid-value", "unknown_field")

    def test_rejects_201_bytes_for_task_category(self):
        """task_category exceeding 200 UTF-8 bytes should be rejected."""
        with pytest.raises(ValueError, match="exceeds 200 bytes"):
            _validate_path_segment("a" * 201, "task_category")

    def test_rejects_201_bytes_for_dataset_id(self):
        """dataset_id exceeding 200 UTF-8 bytes should be rejected."""
        with pytest.raises(ValueError, match="exceeds 200 bytes"):
            _validate_path_segment("a" * 201, "dataset_id")

    def test_rejects_151_bytes_for_run_id(self):
        """run_id exceeding 150 UTF-8 bytes should be rejected."""
        with pytest.raises(ValueError, match="exceeds 150 bytes"):
            _validate_path_segment("a" * 151, "run_id")

    def test_accepts_151_bytes_for_dataset_id(self):
        """dataset_id with 151 bytes should be accepted."""
        value = "a" * 151

        assert _validate_path_segment(value, "dataset_id") == value

    def test_counts_utf8_bytes_not_characters(self):
        """Length limits count UTF-8 bytes rather than Unicode characters."""
        with pytest.raises(ValueError, match="exceeds 200 bytes"):
            _validate_path_segment("ą" * 101, "task_category")

    def test_preserves_original_value(self):
        """The helper must not trim or normalize accepted values."""
        value = "my dataset.v1"

        result = _validate_path_segment(value, "dataset_id")

        assert result == value
        assert result is value
