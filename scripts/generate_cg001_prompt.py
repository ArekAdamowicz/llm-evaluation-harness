import argparse
import hashlib
from pathlib import Path


PROMPTS = {
    "1.0": (
        "Write a Python function named calculate_average(numbers: list[float]) -> float "
        "that calculates the arithmetic mean of the numbers in the input list.\n"
        "\n"
        "Requirements:\n"
        "- Return the arithmetic mean as a float.\n"
        '- If the input list is empty, raise a ValueError with the exact message: "numbers must not be empty".\n'
        "- Do not modify the original input list.\n"
        "- Include type annotations.\n"
        "- Include a descriptive docstring explaining the function's purpose and behavior.\n"
    ),
    "1.1": (
        "Write a Python function named calculate_average(numbers: list[float]) -> float "
        "that calculates the arithmetic mean of the numbers in the input list.\n"
        "\n"
        "Requirements:\n"
        "- Accept a non-empty Python list containing integers or floating-point numbers.\n"
        "- Return the arithmetic mean as a finite Python float.\n"
        '- If the input is not a list, raise a TypeError with the exact message: "numbers must be a list".\n'
        '- If the input list is empty, raise a ValueError with the exact message: "numbers must not be empty".\n'
        '- Reject unsupported element types, including strings, None, and Boolean values. Raise a TypeError with the exact message: "all elements must be int or float, excluding bool".\n'
        '- Reject NaN values with a ValueError and the exact message: "numbers must not contain NaN values".\n'
        '- Reject positive and negative Infinity values with a ValueError and the exact message: "numbers must not contain infinite values".\n'
        "- Calculate the arithmetic mean accurately, including cases involving floating-point cancellation and very large values.\n"
        "- Do not raise an overflow error merely because an intermediate sum exceeds the floating-point range if the final mean is representable as a finite float.\n"
        '- If the final mean cannot be represented as a finite float, raise a ValueError with the exact message: "calculation resulted in overflow".\n'
        "- The result must be independent of the order of valid input elements, within normal floating-point tolerance.\n"
        "- Adding a constant to every input element must increase the calculated mean by that constant, within normal floating-point tolerance.\n"
        "- Do not modify the original input list.\n"
        "- Include type annotations.\n"
        "- Include a descriptive docstring explaining the function's purpose, accepted inputs, return value, and possible exceptions.\n"
        "- The implementation must satisfy all requirements without relying on a specific numerical summation algorithm.\n"
    ),
}


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate a versioned CG-001 prompt artifact."
    )
    parser.add_argument(
        "--version",
        choices=PROMPTS.keys(),
        default="1.0",
        help="CG-001 prompt version to generate (default: 1.0).",
    )
    args = parser.parse_args()

    prompt = PROMPTS[args.version]

    path = Path(
        f"docs/test-cases/prompts/CG-001_v{args.version}.txt"
    )
    path.parent.mkdir(parents=True, exist_ok=True)

    path.write_bytes(prompt.encode("utf-8"))

    file_hash = hashlib.sha256(path.read_bytes()).hexdigest()

    print(f"Prompt file: {path}")
    print(f"Bytes: {len(path.read_bytes())}")
    print(f"SHA-256: {file_hash}")


if __name__ == "__main__":
    main()
