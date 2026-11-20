import math


def assert_numeric_close(
    actual: float,
    expected: float,
    *,
    rel_tol: float = 1e-9,
    abs_tol: float = 1e-12,
) -> None:
    """
    Assert that the actual numerical result is close to the expected value.

    Both actual and expected must be integers or floats, excluding bool.
    Boolean and non-finite numerical values are rejected.

    Args:
        actual: The numerical result produced by the system under test.
        expected: The expected numerical result.
        rel_tol: Maximum relative difference. Defaults to 1e-9.
        abs_tol: Maximum absolute difference. Defaults to 1e-12.

    Raises:
        AssertionError: If actual or expected is invalid, non-finite,
            or the values are not sufficiently close.
        TypeError: If either tolerance is not an integer or float,
            excluding bool.
        ValueError: If either tolerance is negative or non-finite.
    """

    # Validate actual value
    if type(actual) is bool:
        raise AssertionError("Boolean result is not a valid numerical result")

    if not isinstance(actual, (int, float)):
        raise AssertionError("Actual result is not a valid numerical result")

    try:
        if not math.isfinite(actual):
            raise AssertionError("Result is NaN or infinite")
    except OverflowError:
        raise AssertionError("Result cannot be represented as a finite float") from None

    # Validate expected value
    if type(expected) is bool:
        raise AssertionError("Boolean expected value is not valid")

    if not isinstance(expected, (int, float)):
        raise AssertionError("Expected value is not a valid numerical value")

    try:
        if not math.isfinite(expected):
            raise AssertionError("Expected value is NaN or infinite")
    except OverflowError:
        raise AssertionError(
            "Expected value cannot be represented as a finite float"
        ) from None

    # Validate tolerances
    for tolerance in (rel_tol, abs_tol):
        if isinstance(tolerance, bool) or not isinstance(tolerance, (int, float)):
            raise TypeError("Tolerances must be numeric")

        try:
            if not math.isfinite(tolerance):
                raise ValueError("Tolerances must be finite")
        except OverflowError:
            raise ValueError("Tolerances must be finite") from None

    if rel_tol < 0 or abs_tol < 0:
        raise ValueError("Tolerances must be non-negative")

    # Compare values
    if not math.isclose(
        actual,
        expected,
        rel_tol=rel_tol,
        abs_tol=abs_tol,
    ):
        raise AssertionError(f"Expected {expected!r}, got {actual!r}")
