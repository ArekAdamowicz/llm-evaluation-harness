
import math


def calculate_average(numbers: list[float]) -> float:
    """
    Calculate the arithmetic mean of a non-empty list of finite numbers.

    Accepts integers and floats, but rejects booleans and other types.

    Raises:
        TypeError: If the input is not a list or contains invalid elements.
        ValueError: If the list is empty, contains NaN or infinity,
                    or the calculation results in overflow.
    """
    if not isinstance(numbers, list):
        raise TypeError("numbers must be a list")

    if not numbers:
        raise ValueError("numbers must not be empty")

    validated_numbers: list[float] = []

    for value in numbers:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise TypeError(
                "all elements must be int or float, excluding bool"
            )

        try:
            number = float(value)
        except OverflowError:
            raise ValueError("calculation resulted in overflow") from None

        if math.isnan(number):
            raise ValueError("numbers must not contain NaN values")

        if math.isinf(number):
            raise ValueError("numbers must not contain infinite values")

        validated_numbers.append(number)

    try:
        count = len(validated_numbers)

        result = math.fsum(
            number / count for number in validated_numbers
        )

    except OverflowError:
        raise ValueError("calculation resulted in overflow") from None

    if not math.isfinite(result):
        raise ValueError("calculation resulted in overflow")

    return result
