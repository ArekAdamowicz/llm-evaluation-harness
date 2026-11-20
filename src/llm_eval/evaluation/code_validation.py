"""Syntax validation of extracted code (stage 2B)."""

from __future__ import annotations

from typing import Any


def check_syntax(code: str) -> dict[str, Any] | None:
    """Compile code without executing it.

    Returns None when syntax is valid, otherwise a structured parse error.
    """
    if not isinstance(code, str):
        raise TypeError("code must be a string")

    try:
        compile(code, "<llm_generated>", "exec")
    except SyntaxError as exc:
        return {
            "error_type": type(exc).__name__,
            "message": exc.msg,
            "line": exc.lineno,
            "column": exc.offset,
        }
    except ValueError as exc:
        return {
            "error_type": type(exc).__name__,
            "message": str(exc),
            "line": None,
            "column": None,
        }

    return None
