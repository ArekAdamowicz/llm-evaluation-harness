def calculate_average(numbers: list[float]) -> float:
    """
    Calculate the arithmetic mean of the input numbers.

    Raises:
        ValueError: If the input list is empty.
    """
    if not numbers:
        raise ValueError("numbers must not be empty")

    return float(sum(numbers) / len(numbers))
