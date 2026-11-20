"""Contract tests for syntax validation of extracted code (stage 2B).

Contract v1:
- check_syntax(code) returns None when the code compiles,
- otherwise a dict with EXACTLY four keys:
  {"error_type", "message", "line", "column"},
- error_type is type(exc).__name__ (SyntaxError / IndentationError / TabError
  / ValueError), so a mangled-indentation failure stays distinguishable
  from a genuine syntax mistake,
- message is exc.msg for SyntaxError (no duplicated location info)
  and str(exc) for ValueError (which has no .msg),
- line / column come from exc.lineno / exc.offset and may be None,
- empty or whitespace-only code is syntactically valid -> None;
  emptiness is the extraction stage's concern, not this one,
- non-string input raises TypeError.

Safety: compile() does NOT execute code. Execution belongs to stage 4.

Test methodology:
- real compile() is used for behaviour we can trigger deterministically,
- monkeypatch is used where CPython's own behaviour varies by version
  (missing lineno/offset, TabError, exact message pass-through), so we
  test OUR mapping rather than the interpreter's wording.
"""

import json

import pytest

from llm_eval.evaluation.code_validation import check_syntax

VALID_CODE = (
    "def calculate_average(numbers):\n"
    "    if not numbers:\n"
    '        raise ValueError("numbers must not be empty")\n'
    "    return sum(numbers) / len(numbers)"
)

RICH_VALID_CODE = (
    "import math\n"
    "from functools import lru_cache\n"
    "\n"
    "@lru_cache(maxsize=None)\n"
    "def helper(value):\n"
    "    return value\n"
    "\n"
    "class Stats:\n"
    "    def calculate_average(self, numbers):\n"
    "        return math.fsum(numbers) / len(numbers)\n"
)

_MODULE = "llm_eval.evaluation.code_validation"


# --------------------------------------------------------------------------
# valid code
# --------------------------------------------------------------------------


class TestValidCode:
    def test_valid_function(self):
        assert check_syntax(VALID_CODE) is None

    def test_valid_code_with_import_class_and_decorator(self):
        assert check_syntax(RICH_VALID_CODE) is None

    @pytest.mark.parametrize("code", ["", "\n", "\n\n", "   \n\n"])
    def test_empty_and_whitespace_only_are_valid(self, code):
        """Empty source is valid Python; extraction rejects emptiness."""
        assert check_syntax(code) is None

    def test_comment_only_code_is_valid(self):
        assert check_syntax("# nothing implemented yet") is None

    def test_valid_code_without_required_function_is_valid(self):
        """Syntax validation does not check semantics or completeness."""
        code = "def compute_mean(values):\n    return sum(values) / len(values)"
        assert check_syntax(code) is None


# --------------------------------------------------------------------------
# real syntax errors
# --------------------------------------------------------------------------


class TestRealSyntaxErrors:
    def test_unclosed_parenthesis(self):
        """The unclosed bracket and EOF are both on line 2, so the reported
        line number is unambiguous regardless of CPython's convention.
        """
        code = (
            "def calculate_average(numbers):\n"
            "    return sum(numbers) / len(numbers"
        )
        result = check_syntax(code)

        assert result is not None
        assert result["error_type"] == "SyntaxError"
        assert result["line"] == 2
        assert isinstance(result["message"], str)
        assert result["message"]

    def test_missing_colon_reports_offending_line(self):
        code = (
            "import math\n"
            "def calculate_average(numbers)\n"
            "    return 0.0\n"
        )
        result = check_syntax(code)

        assert result is not None
        assert result["error_type"] == "SyntaxError"
        assert result["line"] == 2

    def test_error_on_fourth_line(self):
        code = (
            "import math\n"
            "\n"
            "def calculate_average(numbers):\n"
            "    return math.fsum(numbers) /\n"
        )
        result = check_syntax(code)

        assert result is not None
        assert result["error_type"] == "SyntaxError"
        assert result["line"] == 4

    def test_indentation_error_is_regression_case_for_dedent(self):
        """This is exactly what an un-dedented indented fence produces.

        The error_type must stay 'IndentationError', not 'SyntaxError',
        so the report can distinguish harness-mangled indentation from
        a genuine syntax mistake by the model.
        """
        code = (
            "import math\n"
            "  def calculate_average(numbers):\n"
            "      return math.fsum(numbers) / len(numbers)"
        )
        result = check_syntax(code)

        assert result is not None
        assert result["error_type"] == "IndentationError"
        assert result["line"] == 2


# --------------------------------------------------------------------------
# error mapping (controlled exceptions, version-independent)
# --------------------------------------------------------------------------


class TestErrorMapping:
    def test_missing_position_maps_to_none(self, monkeypatch):
        def fake_compile(*args, **kwargs):
            error = SyntaxError("boom")
            error.msg = "boom"
            error.lineno = None
            error.offset = None
            raise error

        # compile is a builtin, not a module attribute -> raising=False
        monkeypatch.setattr(f"{_MODULE}.compile", fake_compile, raising=False)

        assert check_syntax(VALID_CODE) == {
            "error_type": "SyntaxError",
            "message": "boom",
            "line": None,
            "column": None,
        }

    def test_tab_error_class_name_is_preserved(self, monkeypatch):
        def fake_compile(*args, **kwargs):
            error = TabError("inconsistent use of tabs and spaces")
            error.msg = "inconsistent use of tabs and spaces"
            error.lineno = 3
            error.offset = 1
            raise error

        monkeypatch.setattr(f"{_MODULE}.compile", fake_compile, raising=False)

        result = check_syntax(VALID_CODE)

        assert result["error_type"] == "TabError"
        assert result["line"] == 3
        assert result["column"] == 1

    def test_message_uses_msg_not_str(self, monkeypatch):
        """str(exc) would append '(<llm_generated>, line 7)'."""

        def fake_compile(*args, **kwargs):
            error = SyntaxError("sentinel message")
            error.msg = "sentinel message"
            error.filename = "<llm_generated>"
            error.lineno = 7
            error.offset = 3
            raise error

        monkeypatch.setattr(f"{_MODULE}.compile", fake_compile, raising=False)

        result = check_syntax(VALID_CODE)

        assert result["message"] == "sentinel message"
        assert result["line"] == 7
        assert result["column"] == 3

    def test_value_error_message_uses_str(self, monkeypatch):
        """ValueError has no .msg / .lineno / .offset."""

        def fake_compile(*args, **kwargs):
            raise ValueError("sentinel value error")

        monkeypatch.setattr(f"{_MODULE}.compile", fake_compile, raising=False)

        assert check_syntax(VALID_CODE) == {
            "error_type": "ValueError",
            "message": "sentinel value error",
            "line": None,
            "column": None,
        }


# --------------------------------------------------------------------------
# null bytes
# --------------------------------------------------------------------------


class TestNullBytes:
    def test_null_byte_does_not_abort_the_run(self):
        result = check_syntax("def calculate_average(numbers):\n    return 0.0\x00")

        assert result is not None
        assert result["error_type"] == "SyntaxError"
        assert result["line"] is None
        assert result["column"] is None
        assert isinstance(result["message"], str)
        assert result["message"]


# --------------------------------------------------------------------------
# safety: nothing is executed
# --------------------------------------------------------------------------


class TestNoExecution:
    def test_module_level_raise_is_not_triggered(self):
        code = (
            "raise RuntimeError('this must never run')\n"
            "def calculate_average(numbers):\n"
            "    return 0.0"
        )
        assert check_syntax(code) is None

    def test_module_level_zero_division_is_not_triggered(self):
        code = (
            "value = 1 / 0\n"
            "def calculate_average(numbers):\n"
            "    return 0.0"
        )
        assert check_syntax(code) is None


# --------------------------------------------------------------------------
# compile contract
# --------------------------------------------------------------------------


class TestCompileContract:
    def test_compile_receives_expected_filename_and_mode(self, monkeypatch):
        captured = {}
        real_compile = compile

        def spy(source, filename, mode, *args, **kwargs):
            captured["filename"] = filename
            captured["mode"] = mode
            return real_compile(source, filename, mode, *args, **kwargs)

        monkeypatch.setattr(f"{_MODULE}.compile", spy, raising=False)

        assert check_syntax(VALID_CODE) is None
        assert captured["filename"] == "<llm_generated>"
        assert captured["mode"] == "exec"


# --------------------------------------------------------------------------
# input validation
# --------------------------------------------------------------------------


class TestInputValidation:
    @pytest.mark.parametrize("value", [None, 123, 1.5, b"code", [], {}])
    def test_non_string_raises_type_error(self, value):
        """Must be rejected before compile(), which accepts bytes."""
        with pytest.raises(TypeError, match="code must be a string"):
            check_syntax(value)


# --------------------------------------------------------------------------
# contract shape
# --------------------------------------------------------------------------


class TestContractShape:
    def test_exactly_four_keys(self):
        result = check_syntax("def calculate_average(numbers)\n    pass")

        assert set(result) == {"error_type", "message", "line", "column"}

    def test_no_text_field(self):
        result = check_syntax("def calculate_average(numbers)\n    pass")

        assert "text" not in result

    def test_field_types(self):
        result = check_syntax("def calculate_average(numbers)\n    pass")

        assert isinstance(result["error_type"], str)
        assert isinstance(result["message"], str)
        assert result["line"] is None or isinstance(result["line"], int)
        assert result["column"] is None or isinstance(result["column"], int)

    def test_result_is_json_serializable(self):
        result = check_syntax("def calculate_average(numbers)\n    pass")

        json.dumps(result, allow_nan=False)
