import math
from fractions import Fraction


def calculate_average(numbers: list[float]) -> float:
    """
    Calculate the arithmetic mean of a non-empty list of finite numbers.

    Accepts integers and floats, including arbitrarily large integers.
    Booleans and other unsupported types are rejected.

    The calculation uses exact rational arithmetic to avoid losing
    information during intermediate calculations.

    Returns:
        float: The arithmetic mean as a finite Python float.

    Raises:
        TypeError: If the input is not a list or contains invalid elements.
        ValueError: If the list is empty, contains NaN or infinity,
                    or the final result cannot be represented as a
                    finite Python float.
    """
    if not isinstance(numbers, list):
        raise TypeError("numbers must be a list")

    if not numbers:
        raise ValueError("numbers must not be empty")

    # Validate all element types before numerical conversion.
    for value in numbers:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise TypeError("all elements must be int or float, excluding bool")

    # Validate special floating-point values.
    for value in numbers:
        if isinstance(value, float):
            if math.isnan(value):
                raise ValueError("numbers must not contain NaN values")

            if math.isinf(value):
                raise ValueError("numbers must not contain infinite values")

    # Convert values to exact rational representations.
    exact_numbers = [Fraction(value) for value in numbers]

    # Calculate the exact mathematical mean.
    exact_mean = sum(exact_numbers, Fraction(0)) / len(exact_numbers)

    # Convert only the final result to a Python float.
    try:
        result = float(exact_mean)
    except OverflowError:
        raise ValueError("calculation resulted in overflow") from None

    if not math.isfinite(result):
        raise ValueError("calculation resulted in overflow")

    return result
