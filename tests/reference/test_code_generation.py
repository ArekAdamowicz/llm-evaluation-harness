import math
from copy import deepcopy
from inspect import signature

import pytest

from llm_eval.evaluation.comparisons import assert_numeric_close
from llm_eval.reference.code_generation import calculate_average


# ============================================================
# CG-001 v1.0: Basic functional tests
# ============================================================

@pytest.mark.parametrize(
    ("numbers", "expected"),
    [
        ([1.0, 2.0, 3.0], 2.0),       # TD1: standard case
        ([2.5], 2.5),                 # TD2: single element
        ([0.1, 0.2], 0.15),           # TD3: floating-point values
        ([10.0, 10.0, 10.0], 10.0),   # TD4: identical values
        ([-2.5, -7.5], -5.0),         # TD5: negative values
        ([-1.0, 0.0, 1.0], 0.0),      # TD6: mixed signs
        ([0.0, 0.0], 0.0),            # TD7: zero values
        ([1, 2], 1.5),                # TD8: integer inputs
        ([1, 2, 3], 2.0),             # TD10: return type
    ],
)
def test_calculate_average_returns_correct_mean(numbers, expected):
    result = calculate_average(numbers)

    assert type(result) is float
    assert_numeric_close(result, expected)


def test_calculate_average_raises_value_error_for_empty_list():
    # TD9: empty input list
    with pytest.raises(ValueError) as exc_info:
        calculate_average([])

    assert str(exc_info.value) == "numbers must not be empty"


def test_calculate_average_does_not_modify_input_list():
    numbers = [1.0, 2.0, 3.0]
    original_numbers = deepcopy(numbers)

    calculate_average(numbers)

    assert numbers == original_numbers


def test_calculate_average_does_not_modify_input_list_when_exception_is_raised():
    numbers = []
    original_numbers = deepcopy(numbers)

    with pytest.raises(ValueError):
        calculate_average(numbers)

    assert numbers == original_numbers


def test_calculate_average_does_not_modify_input_list_when_validation_fails():
    numbers = [1.0, "2.0", 3.0]
    original_numbers = deepcopy(numbers)

    with pytest.raises(TypeError):
        calculate_average(numbers)

    assert numbers == original_numbers


def test_calculate_average_has_expected_type_annotations():
    function_signature = signature(calculate_average)

    assert list(function_signature.parameters) == ["numbers"]
    assert function_signature.parameters["numbers"].annotation == list[float]
    assert function_signature.return_annotation is float


def test_calculate_average_has_meaningful_docstring():
    doc = calculate_average.__doc__

    assert doc is not None
    assert len(doc.strip()) > 0

    doc_lower = doc.lower()

    assert "arithmetic mean" in doc_lower
    assert "integers and floats" in doc_lower
    assert "booleans" in doc_lower
    assert "typeerror" in doc_lower
    assert "valueerror" in doc_lower
    assert "empty" in doc_lower


# ============================================================
# CG-001 v1.1: Input validation
# ============================================================

@pytest.mark.parametrize(
    "numbers",
    [
        ["1", 2],
        [None],
        [True],
        [False],
        [object()],
    ],
)
def test_calculate_average_rejects_invalid_types(numbers):
    with pytest.raises(TypeError) as exc_info:
        calculate_average(numbers)

    assert str(exc_info.value) == (
        "all elements must be int or float, excluding bool"
    )


@pytest.mark.parametrize(
    "numbers",
    [
        None,
        (),
        (1, 2, 3),
        "123",
        123,
    ],
)
def test_calculate_average_rejects_non_list_input(numbers):
    with pytest.raises(TypeError) as exc_info:
        calculate_average(numbers)

    assert str(exc_info.value) == "numbers must be a list"


# ============================================================
# CG-001 v1.1: NaN and Infinity validation
# ============================================================

def test_calculate_average_rejects_nan():
    with pytest.raises(ValueError) as exc_info:
        calculate_average([1.0, float("nan")])

    assert str(exc_info.value) == "numbers must not contain NaN values"


@pytest.mark.parametrize(
    "value",
    [
        float("inf"),
        float("-inf"),
    ],
)
def test_calculate_average_rejects_infinity(value):
    with pytest.raises(ValueError) as exc_info:
        calculate_average([1.0, value])

    assert str(exc_info.value) == "numbers must not contain infinite values"


# ============================================================
# CG-001 v1.1: Numerical precision
# ============================================================

def test_calculate_average_handles_floating_point_precision():
    numbers = [1e16, 1.0, -1e16]

    result = calculate_average(numbers)

    assert_numeric_close(result, 1 / 3)


def test_calculate_average_preserves_small_values_with_large_cancellation():
    numbers = [1e308, -1e308, 1e-300]
    expected = 1e-300 / 3

    result = calculate_average(numbers)

    assert_numeric_close(
        result,
        expected,
        abs_tol=0.0,
    )


# ============================================================
# CG-001 v1.1: Overflow protection
# ============================================================

def test_calculate_average_handles_intermediate_overflow():
    numbers = [1e308, 1e308]

    result = calculate_average(numbers)

    assert result == 1e308
    assert math.isfinite(result)


@pytest.mark.parametrize(
    "numbers",
    [
        [10**400],
        [10**1000],
    ],
)
def test_calculate_average_rejects_unrepresentable_mean(numbers):
    with pytest.raises(ValueError) as exc_info:
        calculate_average(numbers)

    assert str(exc_info.value) == "calculation resulted in overflow"


# ============================================================
# CG-001 v1.1: Metamorphic properties
# ============================================================

def test_calculate_average_is_order_independent():
    numbers = [1e16, 1.0, -1e16]
    reversed_numbers = list(reversed(numbers))

    result_original = calculate_average(numbers)
    result_reversed = calculate_average(reversed_numbers)

    assert_numeric_close(result_original, result_reversed)


def test_calculate_average_obeys_shift_invariance():
    numbers = [1.25, 2.5, 4.75]
    shift = 1000.0

    original_average = calculate_average(numbers)
    shifted_average = calculate_average(
        [number + shift for number in numbers]
    )

    assert_numeric_close(
        shifted_average,
        original_average + shift,
    )


# ============================================================
# CG-001 v1.2: Arbitrarily large integer inputs
# ============================================================

def test_calculate_average_handles_large_integer_cancellation():
    numbers = [10**400, -(10**400), 1]

    result = calculate_average(numbers)

    assert_numeric_close(result, 1 / 3)


def test_calculate_average_handles_large_integer_cancellation_with_float():
    numbers = [10**400, -(10**400), 0.5]

    result = calculate_average(numbers)

    assert_numeric_close(result, 0.5 / 3)


def test_calculate_average_handles_large_integer_cancellation_independently_of_order():
    numbers = [10**400, 1, -(10**400)]
    reversed_numbers = list(reversed(numbers))

    result_original = calculate_average(numbers)
    result_reversed = calculate_average(reversed_numbers)

    assert_numeric_close(result_original, 1 / 3)
    assert_numeric_close(result_reversed, 1 / 3)


def test_calculate_average_validates_all_element_types_before_numeric_conversion():
    numbers = [10**400, "invalid"]

    with pytest.raises(TypeError) as exc_info:
        calculate_average(numbers)

    assert str(exc_info.value) == (
        "all elements must be int or float, excluding bool"
    )


def test_calculate_average_rejects_unrepresentable_mean_after_large_integer_cancellation():
    numbers = [10**400, 10**400, -(10**400)]

    with pytest.raises(ValueError) as exc_info:
        calculate_average(numbers)

    assert str(exc_info.value) == "calculation resulted in overflow"
