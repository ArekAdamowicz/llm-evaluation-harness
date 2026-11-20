"""Code extraction from LLM responses for CG-001 (stage 2A).

Selection contract v1:
- only Markdown fenced blocks are considered (no fence -> None),
- only Python blocks are considered (python / py / python3, case-insensitive),
- a block must define REQUIRED_FUNCTION to be a candidate,
- exactly one candidate -> that block,
- more than one candidate -> first one + ambiguous=True,
- no candidate -> None.

Block grammar v1 (deliberately simpler than CommonMark):
- an opening marker is a line whose whitespace-stripped form starts with ```,
- the NEXT fence marker closes the block, even if it carries an info string,
- leading whitespace before a marker is allowed,
- a block left open at end of input is discarded.

Content rule v1:
- N is the number of ASCII spaces before the opening marker;
- leading whitespace before the marker is ignored when recognizing the fence,
  but tabs do not contribute to N;
- content lines are dedented by up to N leading ASCII spaces;
- tabs are never removed by the dedent operation;
- outer whitespace is then stripped;
- relative indentation inside the block is preserved;
- indentation beyond N spaces is preserved, even if this results in
  syntactically invalid Python code.

This is NOT textwrap.dedent(): that would remove the common prefix of the
code lines, which is empty whenever a line sits at column zero (e.g. inside
a triple-quoted string), leaving top-level statements indented.

Known limitations, accepted for v1:
- the function detector is a regex, not a Python parser: a line starting
  with `def calculate_average(` inside a triple-quoted string IS treated
  as a definition;
- an unclosed fence can swallow the opening marker of the next block;
  there is no recovery;
- unfenced code, tilde fences and nested fences are not supported;
- indentation beyond the opening fence indentation is not corrected.
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from typing import Any

REQUIRED_FUNCTION = "calculate_average"

_FENCE = "```"
_PYTHON_TAGS = frozenset({"python", "py", "python3"})
_FUNCTION_PATTERN = re.compile(
    rf"^\s*def\s+{re.escape(REQUIRED_FUNCTION)}\s*\(",
    re.MULTILINE,
)


def _normalize_newlines(text: str) -> str:
    """Normalize CRLF and CR to LF so identical content extracts identically."""
    return text.replace("\r\n", "\n").replace("\r", "\n")


def _leading_spaces(line: str) -> int:
    """Count leading ASCII spaces only; tabs are not counted."""
    return len(line) - len(line.lstrip(" "))


def _is_fence_marker(line: str) -> bool:
    """Return whether a line starts with a fence after leading whitespace."""
    return line.lstrip().startswith(_FENCE)


def _language_tag(marker_line: str) -> str:
    """Return the lowercased first token of the info string, or ''."""
    info = marker_line.lstrip()[len(_FENCE) :].strip()
    if not info:
        return ""
    return info.split()[0].lower()


def _dedent(line: str, indent: int) -> str:
    """Remove up to `indent` leading ASCII spaces from a single line."""
    return line[min(indent, _leading_spaces(line)) :]


def _iter_blocks(text: str) -> Iterator[tuple[str, str]]:
    """Yield (language, code) for every closed fenced block, in order.

    A block left open at end of input is discarded. Since no further fence
    marker can exist after it, scanning stops there.
    """
    lines = text.split("\n")
    index = 0

    while index < len(lines):
        if not _is_fence_marker(lines[index]):
            index += 1
            continue

        indent = _leading_spaces(lines[index])
        language = _language_tag(lines[index])

        closing = index + 1
        while closing < len(lines) and not _is_fence_marker(lines[closing]):
            closing += 1

        if closing >= len(lines):
            return

        content = [_dedent(line, indent) for line in lines[index + 1 : closing]]
        yield language, "\n".join(content).strip()

        index = closing + 1


def extract_code_block(raw_output: str) -> dict[str, Any] | None:
    """Extract the Python block that defines REQUIRED_FUNCTION.

    Args:
        raw_output: Full, unmodified model response.

    Returns:
        {"code": str, "language": "python"} when exactly one block qualifies,
        the same plus {"ambiguous": True} when several qualify (first is used),
        or None when no block qualifies.

    Raises:
        TypeError: If raw_output is not a string.
    """
    if not isinstance(raw_output, str):
        raise TypeError("raw_output must be a string")

    candidates = [
        code
        for language, code in _iter_blocks(_normalize_newlines(raw_output))
        if language in _PYTHON_TAGS and code and _FUNCTION_PATTERN.search(code)
    ]

    if not candidates:
        return None

    result: dict[str, Any] = {
        "code": candidates[0],
        "language": "python",
    }

    if len(candidates) > 1:
        result["ambiguous"] = True

    return result
