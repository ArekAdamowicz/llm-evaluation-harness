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

# Maximum allowed bytes for each path segment when encoded as UTF-8
_PATH_SEGMENT_LIMITS = {
    "task_category": 200,
    "dataset_id": 200,
    "run_id": 150,
}


def _validate_path_segment(value: Any, field_name: str) -> str:
    """Validate that a value is a safe path segment.

    Args:
        value: Value to validate (must be str)
        field_name: Name of the field (for error messages)

    Returns:
        The validated value (unchanged)

    Raises:
        ValueError: If value is invalid
    """
    # Check if field_name is known
    if field_name not in _PATH_SEGMENT_LIMITS:
        raise ValueError(f"Unknown field name: {field_name}")

    # Type check. ValueError is intentional: all invalid path segments share one validation contract.
    if not isinstance(value, str):
        raise ValueError(f"Invalid {field_name}: must be a string")  # noqa: TRY004

    # Empty check
    if not value:
        raise ValueError(f"Invalid {field_name}: cannot be empty")

    # Whitespace check
    if value != value.strip():
        raise ValueError(
            f"Invalid {field_name}: cannot have leading or trailing whitespace"
        )

    # Path separator check (before . and ..)
    if "/" in value or "\\" in value:
        raise ValueError(f"Invalid {field_name}: contains path separator")

    # Reserved names check (. and ..)
    if value in (".", ".."):
        raise ValueError(f"Invalid {field_name}: cannot be '.' or '..'")

    # Control characters check (C0 and C1)
    for char in value:
        code = ord(char)
        if code < 32 or (127 <= code < 160):
            raise ValueError(f"Invalid {field_name}: contains control characters")

    # Windows forbidden characters check
    if any(char in value for char in '<>:"|?*'):
        raise ValueError(
            f"Invalid {field_name}: contains characters not allowed on Windows"
        )

    # Trailing dot check (Windows restriction)
    if value.endswith("."):
        raise ValueError(f"Invalid {field_name}: cannot end with a dot")

    # UTF-8 length check
    try:
        encoded_length = len(value.encode("utf-8"))
    except UnicodeEncodeError as e:
        raise ValueError(
            f"Invalid {field_name}: contains invalid Unicode characters"
        ) from e

    max_bytes = _PATH_SEGMENT_LIMITS[field_name]
    if encoded_length > max_bytes:
        raise ValueError(
            f"Invalid {field_name}: exceeds {max_bytes} bytes when encoded as UTF-8"
        )

    return value


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
        ValueError: If run_id mismatch, JSON serialization fails, or path segments are invalid.
        OSError: If file operations fail.
    """
    # Validate all path segments FIRST (before any other operations)
    if task_category is not None:
        task_category = _validate_path_segment(task_category, "task_category")

    dataset_id = _validate_path_segment(run.dataset_id, "dataset_id")
    run_id = _validate_path_segment(run.run_id, "run_id")

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
    started_date = run.started_at.astimezone(timezone.utc).strftime("%Y-%m-%d")
    filename = f"run_{started_date}_{run_id}.json"

    # Directory structure
    if task_category is not None:
        dataset_dir = root / task_category / dataset_id
    else:
        dataset_dir = root / dataset_id

    dataset_dir.mkdir(parents=True, exist_ok=True)

    target_path = dataset_dir / filename

    # Atomic write: write to temp file, then replace
    fd, temp_path = tempfile.mkstemp(
        dir=dataset_dir,
        prefix=".tmp_",
        suffix=".json",
    )

    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(json_content)

        os.replace(temp_path, target_path)
    except Exception:
        if os.path.exists(temp_path):
            os.unlink(temp_path)
        raise

    return target_path
