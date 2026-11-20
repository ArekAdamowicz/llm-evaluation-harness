"""Tests for llm_eval.results.storage."""

import json
import os
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest

from llm_eval.results.models import (
    ErrorInfo,
    EvaluationRun,
    Metrics,
    TestResult,
    TestStatus,
)
from llm_eval.results.storage import (
    RESULTS_SCHEMA_VERSION,
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
        
        # Should not raise
        json_str = json.dumps(doc, allow_nan=False)
        assert json_str is not None
        
        # Round-trip
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
        assert saved_path.name.startswith(f"run_{run.started_at.strftime('%Y-%m-%d')}_{run.run_id}")
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
        
        # tmp_path/results doesn't exist yet
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
        # Run started yesterday
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
            metadata={"note": "测试"},  # Chinese characters
        )
        
        saved_path = save_run(run, [result], tmp_path)
        
        # Should be readable with UTF-8
        with open(saved_path, encoding="utf-8") as f:
            content = f.read()
        
        assert "测试" in content
    
    def test_save_no_temp_file_on_success(self, tmp_path):
        """No temporary files remain after successful save."""
        run = EvaluationRun(dataset_id="CG-001")
        result = TestResult(run_id=run.run_id, status=TestStatus.PASS)
        
        saved_path = save_run(run, [result], tmp_path)
        
        # Check no .tmp_ files in directory
        temp_files = list(saved_path.parent.glob(".tmp_*"))
        assert len(temp_files) == 0
    
    def test_save_overwrites_existing(self, tmp_path):
        """save_run can overwrite existing file with same name."""
        run = EvaluationRun(dataset_id="CG-001")
        result1 = TestResult(run_id=run.run_id, status=TestStatus.PASS, actual_result=1.0)
        result2 = TestResult(run_id=run.run_id, status=TestStatus.PASS, actual_result=2.0)
        
        path1 = save_run(run, [result1], tmp_path)
        path2 = save_run(run, [result2], tmp_path)
        
        assert path1 == path2
        
        # Should contain result2, not result1
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
        
        # Should be valid JSON
        with open(saved_path, encoding="utf-8") as f:
            data = json.load(f)
        
        # Check tagged format
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
        
        # Check that all digits are present
        assert str(large_int) in content
        assert str(-large_int) in content
        
        # Verify round-trip
        data = json.loads(content)
        numbers = data["results"][0]["input_data"]["numbers"]
        assert numbers[0] == large_int
        assert numbers[1] == -large_int
    
    def test_atomic_write_cleanup_on_failure(self, tmp_path):
        """No temporary files remain after os.replace() failure."""
        run = EvaluationRun(dataset_id="CG-001")
        result = TestResult(run_id=run.run_id, status=TestStatus.PASS)
        
        # Mock os.replace to raise an exception
        with patch("llm_eval.results.storage.os.replace", side_effect=OSError("Mock error")):
            with pytest.raises(OSError, match="Mock error"):
                save_run(run, [result], tmp_path)
        
        # Check no .tmp_ files remain
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
        
        with pytest.raises(ValueError, match="cannot contain path separators"):
            save_run(run, [result], tmp_path, task_category="code/generation")
    
    def test_invalid_task_category_parent_directory(self, tmp_path):
        """task_category as '.' or '..' raises ValueError."""
        run = EvaluationRun(dataset_id="CG-001")
        result = TestResult(run_id=run.run_id, status=TestStatus.PASS)
        
        with pytest.raises(ValueError, match="cannot be '.' or '..'"):
            save_run(run, [result], tmp_path, task_category="..")
    
    def test_date_converted_to_utc(self, tmp_path):
        """Date in filename is converted to UTC regardless of timezone."""
        # Run started at 23:00 UTC-5 (which is 04:00 UTC next day)
        tz_minus_5 = timezone(timedelta(hours=-5))
        local_time = datetime(2026, 11, 20, 23, 0, 0, tzinfo=tz_minus_5)
        
        run = EvaluationRun(
            dataset_id="CG-001",
            started_at=local_time,
        )
        result = TestResult(run_id=run.run_id, status=TestStatus.PASS)
        
        saved_path = save_run(run, [result], tmp_path)
        
        # Should use UTC date (2026-11-21), not local date (2026-11-20)
        assert "2026-11-21" in saved_path.name
