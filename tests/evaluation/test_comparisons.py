import pytest

from llm_eval.evaluation.comparisons import assert_numeric_close


def test_assert_numeric_close_rejects_boolean_true():
    with pytest.raises(
        AssertionError,
        match="Boolean result is not a valid numerical result",
    ):
        assert_numeric_close(True, 1.0)


def test_assert_numeric_close_rejects_boolean_false():
    with pytest.raises(
        AssertionError,
        match="Boolean result is not a valid numerical result",
    ):
        assert_numeric_close(False, 0.0)


def test_assert_numeric_close_rejects_non_numeric():
    with pytest.raises(
        AssertionError,
        match="Actual result is not a valid numerical result",
    ):
        assert_numeric_close("1.0", 1.0)


def test_assert_numeric_close_accepts_int():
    assert_numeric_close(1, 1.0)


def test_assert_numeric_close_accepts_float():
    assert_numeric_close(1.0, 1.0)


def test_assert_numeric_close_uses_tolerance():
    assert_numeric_close(1.0000000001, 1.0)


def test_assert_numeric_close_fails_on_difference():
    with pytest.raises(
        AssertionError,
        match="Expected 1.0, got 2.0",
    ):
        assert_numeric_close(2.0, 1.0)


@pytest.mark.parametrize(
    "actual",
    [
        float("nan"),
        float("inf"),
        float("-inf"),
    ],
)
def test_assert_numeric_close_rejects_non_finite_values(actual):
    with pytest.raises(
        AssertionError,
        match="Result is NaN or infinite",
    ):
        assert_numeric_close(actual, 1.0)


def test_assert_numeric_close_rejects_boolean_before_calling_isclose(
    monkeypatch,
):
    def unexpected_isclose_call(*args, **kwargs):
        pytest.fail("math.isclose must not be called for boolean results")

    monkeypatch.setattr(
        "llm_eval.evaluation.comparisons.math.isclose",
        unexpected_isclose_call,
    )

    with pytest.raises(
        AssertionError,
        match="Boolean result is not a valid numerical result",
    ):
        assert_numeric_close(True, 1.0)


def test_assert_numeric_close_accepts_custom_tolerance():
    assert_numeric_close(
        1.0000001,
        1.0,
        rel_tol=1e-6,
        abs_tol=0.0,
    )


def test_assert_numeric_close_rejects_value_outside_custom_tolerance():
    with pytest.raises(AssertionError):
        assert_numeric_close(
            1.0000001,
            1.0,
            rel_tol=1e-9,
            abs_tol=0.0,
        )


def test_assert_numeric_close_rejects_integer_too_large_for_float():
    with pytest.raises(
        AssertionError,
        match="Result cannot be represented as a finite float",
    ):
        assert_numeric_close(10**400, 1.0)


@pytest.mark.parametrize("expected", [True, False])
def test_assert_numeric_close_rejects_boolean_expected(expected):
    with pytest.raises(
        AssertionError,
        match="Boolean expected value is not valid",
    ):
        assert_numeric_close(1.0, expected)


@pytest.mark.parametrize("expected", ["1.0", None])
def test_assert_numeric_close_rejects_non_numeric_expected(expected):
    with pytest.raises(
        AssertionError,
        match="Expected value is not a valid numerical value",
    ):
        assert_numeric_close(1.0, expected)


@pytest.mark.parametrize(
    "rel_tol, abs_tol",
    [
        (-1.0, 1e-12),
        (1e-9, -1.0),
    ],
)

def test_assert_numeric_close_rejects_negative_tolerances(
    rel_tol,
    abs_tol,
):
    with pytest.raises(
        ValueError,
        match="Tolerances must be non-negative",
    ):
        assert_numeric_close(
            1.0,
            1.0,
            rel_tol=rel_tol,
            abs_tol=abs_tol,
        )

@pytest.mark.parametrize(
    "rel_tol, abs_tol",
    [
        (float("nan"), 1e-12),
        (float("inf"), 1e-12),
        (1e-9, float("nan")),
        (1e-9, float("inf")),
    ],
)

def test_assert_numeric_close_rejects_non_finite_tolerances(
    rel_tol,
    abs_tol,
):
    with pytest.raises(
        ValueError,
        match="Tolerances must be finite",
    ):
        assert_numeric_close(
            1.0,
            1.0,
            rel_tol=rel_tol,
            abs_tol=abs_tol,
        )

@pytest.mark.parametrize(
    "rel_tol, abs_tol",
    [
        (True, 1e-12),
        (1e-9, False),
        ("1e-9", 1e-12),
        (1e-9, "1e-12"),
    ],
)

def test_assert_numeric_close_rejects_invalid_tolerance_types(
    rel_tol,
    abs_tol,
):
    with pytest.raises(
        TypeError,
        match="Tolerances must be numeric",
    ):
        assert_numeric_close(
            1.0,
            1.0,
            rel_tol=rel_tol,
            abs_tol=abs_tol,
        )

def test_assert_numeric_close_accepts_zero_tolerances_for_equal_values():
    assert_numeric_close(
        1.0,
        1.0,
        rel_tol=0.0,
        abs_tol=0.0,
    )


def test_assert_numeric_close_rejects_difference_with_zero_tolerances():
    with pytest.raises(
        AssertionError,
        match="Expected 1.0, got 1.0000001",
    ):
        assert_numeric_close(
            1.0000001,
            1.0,
            rel_tol=0.0,
            abs_tol=0.0,
        )

def test_assert_numeric_close_validates_actual_before_tolerances():
    with pytest.raises(
        AssertionError,
        match="Boolean result is not a valid numerical result",
    ):
        assert_numeric_close(
            True,
            1.0,
            rel_tol=-1.0,
        )

def test_assert_numeric_close_validates_expected_before_tolerances():
    with pytest.raises(
        AssertionError,
        match="Boolean expected value is not valid",
    ):
        assert_numeric_close(
            1.0,
            True,
            rel_tol=-1.0,
        )

@pytest.mark.parametrize(
    "expected",
    [
        float("nan"),
        float("inf"),
        float("-inf"),
    ],
)
def test_assert_numeric_close_rejects_non_finite_expected(expected):
    with pytest.raises(
        AssertionError,
        match="Expected value is NaN or infinite",
    ):
        assert_numeric_close(1.0, expected)


def test_assert_numeric_close_rejects_integer_expected_too_large_for_float():
    with pytest.raises(
        AssertionError,
        match="Expected value cannot be represented as a finite float",
    ):
        assert_numeric_close(1.0, 10**400)


def test_assert_numeric_close_rejects_tolerance_too_large_for_float():
    with pytest.raises(
        ValueError,
        match="Tolerances must be finite",
    ):
        assert_numeric_close(
            1.0,
            1.0,
            rel_tol=10**400,
        )