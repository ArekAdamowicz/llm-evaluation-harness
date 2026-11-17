
"""Generate the CG-001 prompt artifact and calculate its SHA-256 hash."""

from pathlib import Path
import hashlib

# Exact prompt payload:
# UTF-8 without BOM, LF line endings, one trailing newline.
PROMPT = (
    "Write a Python function named calculate_average(numbers: list[float]) -> float "
    "that calculates the arithmetic mean of the numbers in the input list.\n"
    "\n"
    "Requirements:\n"
    "- Return the arithmetic mean as a float.\n"
    '- If the input list is empty, raise a ValueError with the exact message: "numbers must not be empty".\n'
    "- Do not modify the original input list.\n"
    "- Include type annotations.\n"
    "- Include a descriptive docstring explaining the function's purpose and behavior.\n"
)

path = Path("docs/test-cases/prompts/CG-001_v1.0.txt")
path.parent.mkdir(parents=True, exist_ok=True)

path.write_bytes(PROMPT.encode("utf-8"))

file_hash = hashlib.sha256(path.read_bytes()).hexdigest()

print(f"Prompt file: {path}")
print(f"Bytes: {len(path.read_bytes())}")
print(f"SHA-256: {file_hash}")
