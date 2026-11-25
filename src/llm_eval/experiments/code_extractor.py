class CodeExtractionError(ValueError):
    """Raised when code cannot be extracted unambiguously from a response."""


class CodeExtractor:
    """Extracts Python code from model responses."""

    @staticmethod
    def extract(response_text: str) -> str:
        """Extract Python code from a plain response or a Markdown code block.

        Raises:
            TypeError: If response_text is not a string.
            CodeExtractionError: If the response is empty, contains no code,
                uses an unsupported language, or contains multiple code blocks.
        """
        if not isinstance(response_text, str):
            raise TypeError("response_text must be a string")

        if not response_text.strip():
            raise CodeExtractionError("response is empty")

        lines = response_text.splitlines(keepends=True)
        blocks = []
        current_language = None
        current_code = []
        in_block = False

        for line in lines:
            line_content = line

            if line_content.endswith("\r\n"):
                line_content = line_content[:-2]
            elif line_content.endswith(("\r", "\n")):
                line_content = line_content[:-1]

            if in_block:
                if line_content.strip() == "```":
                    blocks.append((current_language, "".join(current_code)))
                    current_language = None
                    current_code = []
                    in_block = False
                else:
                    current_code.append(line)

                continue

            stripped_line = line_content.lstrip()

            if stripped_line.startswith("```"):
                current_language = stripped_line[3:].strip().lower()
                current_code = []
                in_block = True

        if in_block:
            raise CodeExtractionError("malformed Markdown code block")

        if len(blocks) > 1:
            raise CodeExtractionError("multiple code blocks found")

        if len(blocks) == 1:
            language, code = blocks[0]

            if language not in ("", "python", "py"):
                raise CodeExtractionError(
                    f"unsupported code language: {language}"
                )

            code = code.strip()

            if not code:
                raise CodeExtractionError("code block is empty")

            return code

        if "```" in response_text:
            raise CodeExtractionError("malformed Markdown code block")

        return response_text.strip()


        if "```" in response_text:
            raise CodeExtractionError("malformed Markdown code block")

        return response_text.strip()
