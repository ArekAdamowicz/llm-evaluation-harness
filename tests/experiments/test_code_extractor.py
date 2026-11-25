import pytest

from llm_eval.experiments.code_extractor import (
    CodeExtractionError,
    CodeExtractor,
)


class TestCodeExtractor:
    def test_extracts_plain_python_code(self):
        code = "def calculate_average(numbers):\n    return sum(numbers) / len(numbers)"

        result = CodeExtractor.extract(code)

        assert result == code

    def test_extracts_python_code_from_markdown_fence(self):
        response = (
            "Here is the solution:\n"
            "```python\n"
            "def calculate_average(numbers):\n"
            "    return sum(numbers) / len(numbers)\n"
            "```\n"
            "This function calculates the average."
        )

        result = CodeExtractor.extract(response)

        assert result == (
            "def calculate_average(numbers):\n"
            "    return sum(numbers) / len(numbers)"
        )

    def test_extracts_code_from_unlabeled_markdown_fence(self):
        response = (
            "```\n"
            "def calculate_average(numbers):\n"
            "    return sum(numbers) / len(numbers)\n"
            "```"
        )

        result = CodeExtractor.extract(response)

        assert result == (
            "def calculate_average(numbers):\n"
            "    return sum(numbers) / len(numbers)"
        )

    def test_raises_error_when_multiple_code_blocks_exist(self):
        response = (
            "First example:\n"
            "```python\n"
            "print('first')\n"
            "```\n"
            "Second example:\n"
            "```python\n"
            "print('second')\n"
            "```"
        )

        with pytest.raises(CodeExtractionError):
            CodeExtractor.extract(response)

    def test_raises_error_for_empty_response(self):
        with pytest.raises(CodeExtractionError):
            CodeExtractor.extract("")

    def test_raises_error_for_whitespace_only_response(self):
        with pytest.raises(CodeExtractionError):
            CodeExtractor.extract("   \n\t  ")

    def test_raises_error_for_empty_code_block(self):
        response = "```python\n   \n```"

        with pytest.raises(CodeExtractionError):
            CodeExtractor.extract(response)

    def test_raises_error_for_unsupported_language(self):
        response = "```javascript\nconsole.log('hello');\n```"

        with pytest.raises(CodeExtractionError):
            CodeExtractor.extract(response)

    def test_raises_type_error_for_non_string_input(self):
        with pytest.raises(TypeError):
            CodeExtractor.extract(None)

    def test_accepts_py_language_identifier(self):
        response = "```py\nprint('hello')\n```"

        result = CodeExtractor.extract(response)

        assert result == "print('hello')"

    def test_handles_windows_line_endings(self):
        response = (
            "```python\r\n"
            "def calculate_average(numbers):\r\n"
            "    return sum(numbers) / len(numbers)\r\n"
            "```"
        )

        result = CodeExtractor.extract(response)

        assert result == (
            "def calculate_average(numbers):\r\n"
            "    return sum(numbers) / len(numbers)"
        )

    def test_raises_error_for_unclosed_markdown_fence(self):
        response = "```python\ndef calculate_average(numbers):\n    return 0"

        with pytest.raises(CodeExtractionError):
            CodeExtractor.extract(response)

    def test_preserves_backticks_inside_string_literal(self):
        response = (
            "```python\n"
            'def explain_markdown():\n'
            '    print("Use ``` to format code")\n'
            "```"
        )

        result = CodeExtractor.extract(response)

        assert result == (
            "def explain_markdown():\n"
            '    print("Use ``` to format code")'
        )

    def test_preserves_backticks_inside_comment(self):
        response = (
            "```python\n"
            "def explain_markdown():\n"
            "    # ``` is not a closing marker\n"
            "    return True\n"
            "```"
        )

        result = CodeExtractor.extract(response)

        assert result == (
            "def explain_markdown():\n"
            "    # ``` is not a closing marker\n"
            "    return True"
        )

    def test_accepts_indented_closing_fence(self):
        response = (
            "```python\n"
            "print('hello')\n"
            "   ```   "
        )

        result = CodeExtractor.extract(response)

        assert result == "print('hello')"

    def test_preserves_fence_with_additional_text_inside_code(self):
        response = (
            "```python\n"
            "def example():\n"
            "    # ``` this is not a closing marker\n"
            "    return True\n"
            "```"
        )

        result = CodeExtractor.extract(response)

        assert result == (
            "def example():\n"
            "    # ``` this is not a closing marker\n"
            "    return True"
        )
