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
        "1.2": (
        "Write a Python function named calculate_average(numbers: list[float]) -> float "
        "that calculates the arithmetic mean of the numbers in the input list.\n"
        "\n"
        "Requirements:\n"
        "- Accept a non-empty Python list containing integers or floating-point numbers.\n"
        "- Accept Python integers of arbitrary size, including integers that cannot be represented as finite Python floats.\n"
        "- Reject Boolean values explicitly, even though bool is a subclass of int in Python.\n"
        '- If the input is not a list, raise a TypeError with the exact message: "numbers must be a list".\n'
        '- If the input list is empty, raise a ValueError with the exact message: "numbers must not be empty".\n'
        '- Reject unsupported element types, including strings, None, and Boolean values. Raise a TypeError with the exact message: "all elements must be int or float, excluding bool".\n'
        '- Reject NaN values with a ValueError and the exact message: "numbers must not contain NaN values".\n'
        '- Reject positive and negative Infinity values with a ValueError and the exact message: "numbers must not contain infinite values".\n'
        "- Validate the types of all input elements before performing numerical conversion or calculation.\n"
        "- Calculate the mathematical arithmetic mean without prematurely converting individual integers to floats.\n"
        "- Preserve the contribution of all input values, including cases involving very large integers and cancellation between large positive and negative values.\n"
        "- For floating-point inputs, respect the actual values represented by the supplied Python floats.\n"
        "- Use exact intermediate arithmetic or an equivalent approach that avoids loss of information and intermediate floating-point overflow.\n"
        "- A representable final mean must be returned as a finite Python float, even if individual input values or intermediate calculations exceed the representable range of Python float.\n"
        "- Convert only the final mathematical mean to a Python float, using standard Python float conversion and rounding behavior.\n"
        '- If the final mean cannot be represented as a finite float, raise a ValueError with the exact message: "calculation resulted in overflow".\n'
        "- The result must be independent of the order of valid input elements, within normal floating-point tolerance.\n"
        "- Adding a constant to every input element must increase the calculated mean by that constant, within normal floating-point tolerance.\n"
        "- Do not modify the original input list.\n"
        "- Include type annotations.\n"
        "- Include a descriptive docstring explaining the function's purpose, accepted inputs, return value, and possible exceptions.\n"
        "- The implementation must satisfy all requirements without relying on a specific numerical summation algorithm or library.\n"
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
