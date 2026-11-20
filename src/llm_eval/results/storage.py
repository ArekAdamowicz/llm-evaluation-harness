"""Storage utilities for evaluation results.

Provides functions to build and save evaluation run documents to JSON.
"""

import json
import os
import tempfile
from datetime import timezone
from pathlib import Path
from typing import Any

from llm_eval.results.models import EvaluationRun, TestResult, TestStatus


RESULTS_SCHEMA_VERSION = "1.0"


def build_run_document(
    run: EvaluationRun,
    results: list[TestResult],
) -> dict[str, Any]:
    """Build a JSON-serializable document for an evaluation run.
    
    Args:
        run: The evaluation run metadata.
        results: List of test results associated with this run.
    
    Returns:
        Dictionary ready for JSON serialization.
    
    Raises:
        ValueError: If any result has a different run_id than the run.
    """
    # Validate all results belong to this run
    for result in results:
        if result.run_id != run.run_id:
            raise ValueError(
                f"Result {result.result_id} has run_id {result.run_id}, "
                f"expected {run.run_id}"
            )
    
    # Count statuses
    summary = {
        "total": len(results),
        "PASS": sum(1 for r in results if r.status is TestStatus.PASS),
        "FAIL": sum(1 for r in results if r.status is TestStatus.FAIL),
        "ERROR": sum(1 for r in results if r.status is TestStatus.ERROR),
        "SKIPPED": sum(1 for r in results if r.status is TestStatus.SKIPPED),
    }
    
    return {
        "schema_version": RESULTS_SCHEMA_VERSION,
        "run": run.to_dict(),
        "summary": summary,
        "results": [result.to_dict() for result in results],
    }


def _validate_task_category(task_category: str) -> None:
    """Validate task_category is a safe path segment.
    
    Args:
        task_category: Task category to validate.
    
    Raises:
        ValueError: If task_category is empty or contains path separators.
    """
    if not task_category or not task_category.strip():
        raise ValueError("task_category cannot be empty")
    
    # Reject path separators and parent directory references
    if os.sep in task_category or "/" in task_category or "\\" in task_category:
        raise ValueError(
            f"task_category cannot contain path separators: {task_category}"
        )
    
    if task_category in (".", ".."):
        raise ValueError(
            f"task_category cannot be '.' or '..': {task_category}"
        )


def save_run(
    run: EvaluationRun,
    results: list[TestResult],
    root: Path,
    task_category: str | None = None,
) -> Path:
    """Save evaluation run to JSON file with atomic write.
    
    Creates directory structure:
    - results/<dataset_id>/run_YYYY-MM-DD_<run_id>.json (if task_category is None)
    - results/<task_category>/<dataset_id>/run_YYYY-MM-DD_<run_id>.json (if task_category provided)
    
    Args:
        run: The evaluation run metadata.
        results: List of test results.
        root: Root directory for results (e.g., Path("results")).
        task_category: Optional task category (e.g., "code-generation").
    
    Returns:
        Path to the saved file.
    
    Raises:
        ValueError: If run_id mismatch, JSON serialization fails, or task_category is invalid.
        OSError: If file operations fail.
    """
    # Validate task_category if provided
    if task_category is not None:
        _validate_task_category(task_category)
    
    # Build document (validates run_id consistency)
    document = build_run_document(run, results)
    
    # Serialize to JSON (validates no NaN/Infinity)
    try:
        json_content = json.dumps(
            document,
            allow_nan=False,
            indent=2,
            ensure_ascii=False,
    )
    except (TypeError, ValueError) as e:
        raise ValueError(f"JSON serialization failed: {e}") from e
    
    # Build file path
    # Extract date from started_at converted to UTC
    started_date = run.started_at.astimezone(timezone.utc).strftime("%Y-%m-%d")
    filename = f"run_{started_date}_{run.run_id}.json"
    
    # Directory structure
    if task_category is not None:
        dataset_dir = root / task_category / run.dataset_id
    else:
        dataset_dir = root / run.dataset_id
    
    dataset_dir.mkdir(parents=True, exist_ok=True)
    
    target_path = dataset_dir / filename
    
    # Atomic write: write to temp file, then replace
    # Use same directory to ensure same filesystem (required for os.replace)
    fd, temp_path = tempfile.mkstemp(
        dir=dataset_dir,
        prefix=".tmp_",
        suffix=".json",
    )
    
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(json_content)
        
        # Atomic replace
        os.replace(temp_path, target_path)
    except Exception:
        # Clean up temp file on error
        if os.path.exists(temp_path):
            os.unlink(temp_path)
        raise
    
    return target_path
