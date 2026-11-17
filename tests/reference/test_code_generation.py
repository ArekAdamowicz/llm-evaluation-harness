import math
from copy import deepcopy
from inspect import signature

import pytest

from llm_eval.reference.code_generation import calculate_average


@pytest.mark.parametrize(
    ("numbers", "expected"),
    [
        ([1.0, 2.0, 3.0], 2.0),       # TD1: standard case
        ([2.5], 2.5),                 # TD2: single element
        ([0.1, 0.2], 0.15),           # TD3: floating-point values
        ([10.0, 10.0, 10.0], 10.0),   # TD4: identical values
        ([-2.5, -7.5], -5.0),         # TD5: negative values
        ([-1.0, 0.0, 1.0], 0.0),      # TD6: negative, zero and positive values
        ([0.0, 0.0], 0.0),            # TD7: zero values
        ([1, 2], 1.5),                # TD8: integer inputs
        ([1, 2, 3], 2.0),             # TD10: return type must be float
    ],
)
def test_calculate_average_returns_correct_mean(numbers, expected):
    result = calculate_average(numbers)

    assert type(result) is float
    assert math.isclose(result, expected, rel_tol=1e-9, abs_tol=1e-12)


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


def test_calculate_average_has_expected_type_annotations():
    function_signature = signature(calculate_average)

    assert function_signature.parameters["numbers"].annotation == list[float]
    assert function_signature.return_annotation is float


def test_calculate_average_has_meaningful_docstring():
    doc = calculate_average.__doc__

    assert doc is not None
    assert len(doc.strip()) > 0

    doc_lower = doc.lower()

    assert "empty" in doc_lower
    assert "valueerror" in doc_lower
