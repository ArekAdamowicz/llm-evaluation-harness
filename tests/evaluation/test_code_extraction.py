"""Tests for extracting Python code from LLM responses.

The extraction contract:
- Only fenced Python code blocks are considered.
- Supported language tags: python, py, python3.
- A candidate must define the required function.
- If multiple candidates exist, the first is returned and marked ambiguous.
- Unfenced code and unsupported language blocks are rejected.
- Unclosed fences are discarded.
- Extracted code is dedented according to the opening fence indentation.

Implementation details and known parser limitations are documented in
llm_eval.evaluation.code_extraction.
"""

import json

import pytest

from llm_eval.evaluation.code_extraction import (
    REQUIRED_FUNCTION,
    extract_code_block,
)

VALID_CODE = (
    "def calculate_average(numbers):\n"
    "    if not numbers:\n"
    '        raise ValueError("numbers must not be empty")\n'
    "    return sum(numbers) / len(numbers)"
)

USAGE_ONLY_CODE = "result = calculate_average([1.0, 2.0, 3.0])\nprint(result)"

OTHER_FUNCTION_CODE = (
    "def compute_mean(values):\n"
    "    return sum(values) / len(values)"
)


def fence(code: str, language: str = "python") -> str:
    return f"```{language}\n{code}\n```"

class TestHappyPath:
    def test_extracts_python_code_block(self):
        result = extract_code_block(fence(VALID_CODE))

        assert result == {
            "code": VALID_CODE,
            "language": "python",
        }

    def test_extracts_code_from_response_with_prose(self):
        raw = (
            "Here is the implementation:\n\n"
            f"{fence(VALID_CODE)}\n\n"
            "Let me know if you need anything else."
        )

        result = extract_code_block(raw)

        assert result is not None
        assert result["code"] == VALID_CODE

    def test_extracts_function_from_second_block(self):
        raw = (
            f"{fence(USAGE_ONLY_CODE)}\n\n"
            f"{fence(VALID_CODE)}"
        )

        result = extract_code_block(raw)

        assert result is not None
        assert result["code"] == VALID_CODE

    def test_ignores_usage_block_before_function_definition(self):
        raw = (
            "Example usage:\n"
            f"{fence(USAGE_ONLY_CODE)}\n\n"
            "Implementation:\n"
            f"{fence(VALID_CODE)}"
        )

        result = extract_code_block(raw)

        assert result is not None
        assert result["code"] == VALID_CODE

    def test_preserves_code_content(self):
        code = (
            "import math\n\n"
            "def calculate_average(numbers):\n"
            "    return math.fsum(numbers) / len(numbers)"
        )

        result = extract_code_block(fence(code))

        assert result is not None
        assert result["code"] == code


class TestBlockSelection:
    def test_uses_first_matching_block(self):
        first = VALID_CODE
        second = (
            "def calculate_average(numbers):\n"
            "    return 100.0"
        )

        raw = f"{fence(first)}\n\n{fence(second)}"

        result = extract_code_block(raw)

        assert result is not None
        assert result["code"] == first
        assert result["ambiguous"] is True

    def test_marks_three_matching_blocks_as_ambiguous(self):
        first = VALID_CODE
        second = "def calculate_average(numbers):\n    return 2.0"
        third = "def calculate_average(numbers):\n    return 3.0"

        raw = "\n\n".join(
            [fence(first), fence(second), fence(third)]
        )

        result = extract_code_block(raw)

        assert result is not None
        assert result["code"] == first
        assert result["ambiguous"] is True

    def test_does_not_mark_single_candidate_as_ambiguous(self):
        raw = (
            f"{fence(USAGE_ONLY_CODE)}\n\n"
            f"{fence(VALID_CODE)}"
        )

        result = extract_code_block(raw)

        assert result is not None
        assert "ambiguous" not in result

    def test_ignores_non_python_block_before_python_block(self):
        raw = (
            f"{fence(VALID_CODE, 'javascript')}\n\n"
            f"{fence(VALID_CODE)}"
        )

        result = extract_code_block(raw)

        assert result is not None
        assert result["code"] == VALID_CODE
        assert "ambiguous" not in result

    def test_ignores_block_without_required_function(self):
        raw = (
            f"{fence(OTHER_FUNCTION_CODE)}\n\n"
            f"{fence(VALID_CODE)}"
        )

        result = extract_code_block(raw)

        assert result is not None
        assert result["code"] == VALID_CODE

    def test_non_python_matching_block_does_not_create_ambiguity(self):
        raw = (
            f"{fence(VALID_CODE, 'javascript')}\n\n"
            f"{fence(VALID_CODE)}"
        )

        result = extract_code_block(raw)

        assert result is not None
        assert "ambiguous" not in result

    def test_unclosed_block_is_not_a_candidate(self):
        raw = (
            "```python\n"
            f"{VALID_CODE}\n"
        )

        assert extract_code_block(raw) is None


class TestFunctionMatching:
    def test_matches_required_function(self):
        assert extract_code_block(fence(VALID_CODE)) is not None

    def test_matches_function_with_leading_indentation(self):
        code = (
            "    def calculate_average(numbers):\n"
            "        return 0.0"
        )

        result = extract_code_block(fence(code))

        assert result is not None

    def test_matches_whitespace_between_def_and_name(self):
        code = (
            "def   calculate_average(numbers):\n"
            "    return 0.0"
        )

        result = extract_code_block(fence(code))

        assert result is not None

    def test_matches_whitespace_before_opening_parenthesis(self):
        code = (
            "def calculate_average   (numbers):\n"
            "    return 0.0"
        )

        result = extract_code_block(fence(code))

        assert result is not None

    def test_does_not_match_similar_function_name(self):
        code = (
            "def calculate_average_v2(numbers):\n"
            "    return 0.0"
        )

        assert extract_code_block(fence(code)) is None

    def test_does_not_match_function_call(self):
        code = "result = calculate_average([1, 2, 3])"

        assert extract_code_block(fence(code)) is None

    def test_does_not_match_comment_mention(self):
        code = (
            "# def calculate_average(numbers):\n"
            "def compute_mean(numbers):\n"
            "    return 0.0"
        )

        assert extract_code_block(fence(code)) is None

    def test_does_not_match_definition_without_parenthesis(self):
        code = "def calculate_average"

        assert extract_code_block(fence(code)) is None


class TestRejections:
    @pytest.mark.parametrize(
        "raw_output",
        [
            "",
            "   ",
            "Here is the implementation.",
            VALID_CODE,
            f"```text\n{VALID_CODE}\n```",
            f"```json\n{VALID_CODE}\n```",
            f"```bash\n{VALID_CODE}\n```",
            f"```\n{VALID_CODE}\n```",
            f"~~~python\n{VALID_CODE}\n~~~",
            "`def calculate_average(numbers):`",
        ],
    )
    def test_rejects_non_candidate_responses(self, raw_output):
        assert extract_code_block(raw_output) is None

    def test_rejects_empty_python_block(self):
        assert extract_code_block("```python\n```") is None

    def test_rejects_whitespace_only_python_block(self):
        assert extract_code_block("```python\n   \n```") is None

    def test_rejects_comment_only_python_block(self):
        raw = "```python\n# calculate_average is implemented elsewhere\n```"

        assert extract_code_block(raw) is None

    def test_rejects_python_block_without_required_function(self):
        assert extract_code_block(fence(OTHER_FUNCTION_CODE)) is None


class TestLanguageTags:
    @pytest.mark.parametrize(
        "language",
        ["python", "py", "python3", "PYTHON", "Py", "Python3"],
    )
    def test_accepts_supported_language_tags(self, language):
        result = extract_code_block(fence(VALID_CODE, language))

        assert result is not None
        assert result["language"] == "python"
        assert result["code"] == VALID_CODE

    def test_rejects_untagged_fence(self):
        raw = f"```\n{VALID_CODE}\n```"

        assert extract_code_block(raw) is None

    def test_untagged_block_does_not_create_ambiguity(self):
        raw = (
            f"```\n{VALID_CODE}\n```\n\n"
            f"{fence(VALID_CODE)}"
        )

        result = extract_code_block(raw)

        assert result is not None
        assert result["code"] == VALID_CODE
        assert "ambiguous" not in result

    def test_accepts_language_tag_with_additional_info(self):
        raw = f"```python title=solution.py\n{VALID_CODE}\n```"

        result = extract_code_block(raw)

        assert result is not None
        assert result["code"] == VALID_CODE


class TestMalformedInput:
    def test_discards_unclosed_fence(self):
        raw = f"```python\n{VALID_CODE}"

        assert extract_code_block(raw) is None

    def test_unclosed_fence_can_swallow_next_opening_marker(self):
        raw = (
            "```python\n"
            "some incomplete code\n"
            "```python\n"
            f"{VALID_CODE}\n"
            "```"
        )

        assert extract_code_block(raw) is None

    def test_next_fence_marker_closes_block_even_with_info_string(self):
        raw = (
            "```python\n"
            f"{VALID_CODE}\n"
            "```text\n"
            f"{VALID_CODE}\n"
            "```"
        )

        result = extract_code_block(raw)

        assert result is not None
        assert result["code"] == VALID_CODE
        assert "ambiguous" not in result

    def test_normalizes_crlf_newlines(self):
        raw = fence(VALID_CODE).replace("\n", "\r\n")

        result = extract_code_block(raw)

        assert result is not None
        assert result["code"] == VALID_CODE

    def test_normalizes_cr_newlines(self):
        raw = fence(VALID_CODE).replace("\n", "\r")

        result = extract_code_block(raw)

        assert result is not None
        assert result["code"] == VALID_CODE

    def test_ignores_inline_backticks(self):
        raw = (
            "The function is `calculate_average(numbers)`.\n"
            f"{fence(VALID_CODE)}"
        )

        result = extract_code_block(raw)

        assert result is not None
        assert result["code"] == VALID_CODE


class TestDedentRule:
    def test_indented_fence_is_dedented(self):
        raw = (
            "  ```python\n"
            "  def calculate_average(numbers):\n"
            "      return 0.0\n"
            "  ```"
        )

        result = extract_code_block(raw)

        assert result is not None
        assert result["code"] == (
            "def calculate_average(numbers):\n"
            "    return 0.0"
        )

    def test_indented_fence_with_import_is_dedented(self):
        raw = (
            "  ```python\n"
            "  import math\n"
            "  def calculate_average(numbers):\n"
            "      return math.fsum(numbers) / len(numbers)\n"
            "  ```"
        )

        result = extract_code_block(raw)

        assert result is not None
        assert result["code"] == (
            "import math\n"
            "def calculate_average(numbers):\n"
            "    return math.fsum(numbers) / len(numbers)"
        )

    def test_zero_indent_line_defeats_common_prefix_dedent(self):
        """A zero-indented string line must not prevent fence-N dedenting."""
        raw = (
            "  ```python\n"
            '  TEMPLATE = """\n'
            "zero-indent line\n"
            '  """\n'
            "  def calculate_average(numbers):\n"
            "      return 0.0\n"
            "  ```"
        )

        result = extract_code_block(raw)

        assert result is not None
        assert result["code"] == (
            'TEMPLATE = """\n'
            "zero-indent line\n"
            '"""\n'
            "def calculate_average(numbers):\n"
            "    return 0.0"
        )

    def test_removes_up_to_n_spaces_per_line(self):
        """A line with fewer than N leading spaces loses only what it has."""
        raw = (
            "    ```python\n"
            "    def calculate_average(numbers):\n"
            "  \n"
            "        return 0.0\n"
            "    ```"
        )

        result = extract_code_block(raw)

        assert result is not None
        assert result["code"] == (
            "def calculate_average(numbers):\n"
            "\n"
            "    return 0.0"
        )

    def test_tabs_are_not_removed(self):
        """Only spaces are stripped; a tab-indented body stays as it was."""
        raw = (
            "  ```python\n"
            "  def calculate_average(numbers):\n"
            "\treturn 0.0\n"
            "  ```"
        )

        result = extract_code_block(raw)

        assert result is not None
        assert result["code"] == (
            "def calculate_average(numbers):\n"
            "\treturn 0.0"
        )

    def test_n_comes_from_opening_marker_not_closing(self):
        raw = (
            "  ```python\n"
            "  def calculate_average(numbers):\n"
            "      return 0.0\n"
            "```"
        )

        result = extract_code_block(raw)

        assert result is not None
        assert result["code"] == (
            "def calculate_average(numbers):\n"
            "    return 0.0"
        )

    def test_tab_before_marker_is_recognized_but_not_counted(self):
        """Tabs before the marker are recognized but do not contribute to N."""
        raw = (
            "\t```python\n"
            "\tdef calculate_average(numbers):\n"
            "\t\treturn 0.0\n"
            "\t```"
        )

        result = extract_code_block(raw)

        assert result is not None
        assert result["code"] == (
            "def calculate_average(numbers):\n"
            "\t\treturn 0.0"
        )

    def test_preserves_indentation_beyond_fence_indent(self):
        """Indentation beyond the opening fence indentation is preserved."""
        raw = (
            "  ```python\n"
            "  # header\n"
            "    # comment\n"
            "    def calculate_average(numbers):\n"
            "        return 0.0\n"
            "  ```"
        )

        result = extract_code_block(raw)

        assert result is not None
        assert result["code"] == (
            "# header\n"
            "  # comment\n"
            "  def calculate_average(numbers):\n"
            "      return 0.0"
        )

class TestKnownLimitations:
    def test_regex_matches_definition_like_line_inside_triple_quoted_string(self):
        """The regex is not a Python parser and may match string contents."""
        code = (
            'TEMPLATE = """\n'
            "def calculate_average(numbers):\n"
            '"""\n'
            "def compute_mean(numbers):\n"
            "    return 0.0"
        )

        result = extract_code_block(fence(code))

        assert result is not None
        assert result["code"] == code


class TestInputValidation:
    @pytest.mark.parametrize(
        "raw_output",
        [
            None,
            123,
            1.5,
            b"some bytes",
            [],
            {},
        ],
    )
    def test_rejects_non_string_input(self, raw_output):
        with pytest.raises(TypeError, match="raw_output must be a string"):
            extract_code_block(raw_output)


class TestContractShape:
    def test_result_has_exact_keys_for_single_candidate(self):
        result = extract_code_block(fence(VALID_CODE))

        assert result is not None
        assert set(result) == {"code", "language"}

    def test_result_has_ambiguous_key_for_multiple_candidates(self):
        raw = f"{fence(VALID_CODE)}\n\n{fence(VALID_CODE)}"

        result = extract_code_block(raw)

        assert result is not None
        assert set(result) == {"code", "language", "ambiguous"}
        assert result["ambiguous"] is True

    def test_code_is_a_string(self):
        result = extract_code_block(fence(VALID_CODE))

        assert result is not None
        assert isinstance(result["code"], str)

    def test_result_is_json_serializable(self):
        result = extract_code_block(fence(VALID_CODE))

        assert result is not None
        serialized = json.dumps(result)

        assert isinstance(serialized, str)

    def test_required_function_constant(self):
        assert REQUIRED_FUNCTION == "calculate_average"
