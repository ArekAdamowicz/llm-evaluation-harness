# CG-001: calculate_average

## Version History

### v1.0 – Initial Release

- Basic arithmetic mean calculation.
- Empty list validation.
- Type annotations.
- Input immutability.
- Descriptive docstring.

### v1.1 – Numerical Robustness and Extended Validation

- Added validation of input container and element types.
- Added explicit rejection of NaN and positive/negative Infinity.
- Added numerical precision requirements.
- Added overflow protection.
- Added metamorphic testing properties:
  - Shift Invariance.
  - Order Independence.

**Current version:** v1.1

---

## 1. Function Specification

### 1.1 Purpose

Calculate the arithmetic mean of a list of numbers, with robust handling of invalid inputs, special floating-point values, and numerically challenging cases.

### 1.2 Function Signature

```python
def calculate_average(numbers: list[float]) -> float:
```

### 1.3 Parameters

| Parameter | Type | Description |
|---|---|---|
| numbers | list[float] | A non-empty list containing integer or floating-point values |

Integer values are accepted as valid input, even though the function annotation specifies `list[float]`.

Boolean values are not accepted, despite `bool` being a subclass of `int` in Python.

### 1.4 Returns

`float`: The arithmetic mean of the input values.

The returned value must be a finite floating-point number.

### 1.5 Exceptions

The function MUST raise the following exceptions under the specified conditions.

| Exception | Condition | Exact message |
|---|---|---|
| ValueError | Input list is empty | `numbers must not be empty` |
| TypeError | Input is not a list | `numbers must be a list` |
| TypeError | At least one element is not an integer or float, or is a boolean | `all elements must be int or float, excluding bool` |
| ValueError | At least one element is NaN | `numbers must not contain NaN values` |
| ValueError | At least one element is positive or negative Infinity | `numbers must not contain infinite values` |
| ValueError | The final arithmetic mean cannot be represented as a finite float | `calculation resulted in overflow` |

Validation MUST occur before numerical calculation.

The function MUST NOT silently propagate NaN or Infinity into its result.

---

## 2. Functional Requirements

| ID | Requirement | Description | Priority |
|---|---|---|---|
| AC1 | Correctness | Calculate the arithmetic mean correctly for valid input values. | High |
| AC2 | Return Type | Return the result as a Python `float`. | High |
| AC3 | Empty Input | Raise the specified ValueError for an empty list. | High |
| AC4 | Container Validation | Reject inputs that are not lists with TypeError. | High |
| AC5 | Element Validation | Reject unsupported element types and boolean values with TypeError. | High |
| AC6 | NaN Validation | Reject NaN values with ValueError. | High |
| AC7 | Infinity Validation | Reject positive and negative Infinity with ValueError. | High |
| AC8 | Numerical Precision | Correctly handle numerically challenging inputs without catastrophic cancellation. | High |
| AC9 | Overflow Protection | Do not return a non-finite result or reject a representable mean merely because an intermediate sum overflows. | High |
| AC10 | Immutability | Do not modify the original input list. | High |
| AC11 | Type Annotations | Maintain the required function signature and type annotations. | Medium |
| AC12 | Documentation | Include a meaningful docstring describing the function's purpose and behavior. | Medium |
| AC13 | Shift Invariance | Satisfy the shift invariance property for applicable valid inputs. | High |
| AC14 | Order Independence | Produce equivalent results regardless of input element order. | High |

---

## 3. Numerical Precision

The function MUST correctly calculate the arithmetic mean for numerically challenging inputs.

### 3.1 Catastrophic Cancellation

Example:

```python
numbers = [1e16, 1.0, -1e16]
result = calculate_average(numbers)

# Expected: approximately 0.3333333333333333
# Incorrect result: 0.0
```

A naive sequential summation using Python's built-in `sum()` can lose the contribution of smaller values.

The implementation should use a numerically stable summation algorithm.

**Implementation note:** Consider using `math.fsum()` or an equivalent approach. The contract requires numerical correctness, not a specific implementation.

### 3.2 Intermediate Overflow

An intermediate sum may exceed the representable range of float64 even when the final arithmetic mean is representable.

Example:

```python
numbers = [1e308, 1e308]
result = calculate_average(numbers)

# Expected: 1e308
```

The function MUST return the correct finite mean in this case.

An implementation that simply calculates `math.fsum(numbers) / len(numbers)` may fail because the intermediate sum can overflow.

### 3.3 Unrepresentable Final Result

If the final arithmetic mean cannot be represented as a finite Python float, the function MUST raise:

```python
ValueError("calculation resulted in overflow")
```

Example:

```python
numbers = [10**400]
```

The function MUST NOT silently return Infinity.

---

## 4. Metamorphic Testing Properties

Metamorphic testing verifies mathematical relationships between multiple executions instead of relying exclusively on individual expected values.

Both properties MUST hold for applicable valid inputs.

Comparisons MUST use the following numerical tolerance:

```python
rel_tol = 1e-9
abs_tol = 1e-12
```

The test data must be selected so that transformations do not introduce invalid values or unrepresentable results.

### 4.1 Property A: Shift Invariance

Adding a constant `C` to every element of a list should increase the arithmetic mean by exactly `C`.

Mathematical relationship:

```text
mean(numbers + C) = mean(numbers) + C
```

Example:

```python
numbers = [1.0, 2.0, 3.0]
constant = 5.0

shifted = [x + constant for x in numbers]

assert math.isclose(
    calculate_average(shifted),
    calculate_average(numbers) + constant,
    rel_tol=1e-9,
    abs_tol=1e-12
)
```

### 4.2 Property B: Order Independence

Changing the order of elements must not change the mathematical result.

Example:

```python
numbers = [1e16, 1.0, -1e16]
reversed_numbers = list(reversed(numbers))

assert math.isclose(
    calculate_average(numbers),
    calculate_average(reversed_numbers),
    rel_tol=1e-9,
    abs_tol=1e-12
)
```

Order independence is particularly important when evaluating numerical stability.

Naive summation algorithms may produce different results depending on the order in which values are processed.

---

## 5. Usage Examples

### 5.1 Standard Case

```python
calculate_average([1.0, 2.0, 3.0])

# Expected: 2.0
```

### 5.2 Single Element

```python
calculate_average([42.0])

# Expected: 42.0
```

### 5.3 Integer Inputs

```python
calculate_average([1, 2, 3])

# Expected: 2.0
```

### 5.4 Negative Values

```python
calculate_average([-2.5, -7.5])

# Expected: -5.0
```

### 5.5 Numerically Challenging Input

```python
calculate_average([1e16, 1.0, -1e16])

# Expected: approximately 0.3333333333333333
```

### 5.6 Empty Input

```python
calculate_average([])

# Expected:
# ValueError: numbers must not be empty
```

### 5.7 NaN Input

```python
calculate_average([1.0, float("nan"), 3.0])

# Expected:
# ValueError: numbers must not contain NaN values
```

### 5.8 Infinity Input

```python
calculate_average([1.0, float("inf"), 3.0])

# Expected:
# ValueError: numbers must not contain infinite values
```

### 5.9 Invalid Element Type

```python
calculate_average([1.0, "2.0", 3.0])

# Expected:
# TypeError: all elements must be int or float, excluding bool
```

### 5.10 Boolean Input

```python
calculate_average([True, False])

# Expected:
# TypeError: all elements must be int or float, excluding bool
```

---

## 6. Implementation Notes

These notes provide implementation guidance without requiring a specific internal algorithm.

### 6.1 Numerical Precision

Use a numerically stable summation approach, such as `math.fsum()` or an equivalent algorithm.

### 6.2 Input Validation

Validate the input container and its elements before performing numerical calculations.

Boolean values MUST be rejected explicitly.

### 6.3 Special Values

Check for NaN and positive/negative Infinity before calculating the mean.

### 6.4 Overflow Protection

Distinguish between intermediate summation overflow and an unrepresentable final mean.

A representable final mean MUST be returned even if a naive intermediate summation would overflow.

### 6.5 Immutability

Do not sort, filter, or otherwise modify the original input list.

Creating temporary data structures is permitted.

### 6.6 Implementation Independence

The implementation is free to use any algorithm that satisfies the functional requirements.

Evaluation MUST focus on observable behavior and contract compliance rather than requiring an exact match with the reference implementation.

---

## 7. Test Coverage Requirements

The following categories MUST be covered by the evaluation test suite.

| Category | Coverage |
|---|---|
| Basic correctness | Standard cases, single element, identical values |
| Edge cases | Negative values, zeros, mixed signs |
| Input validation | Invalid containers and invalid element types |
| Special values | NaN, positive Infinity, negative Infinity |
| Numerical precision | Catastrophic cancellation |
| Overflow protection | Intermediate overflow and unrepresentable final results |
| Immutability | Input list unchanged after successful execution and exceptions |
| Type annotations | Function signature validation |
| Documentation | Meaningful docstring |
| Metamorphic testing | Shift invariance and order independence |

---

## 8. Evaluation Rules

### 8.1 Expected Results

Expected values MUST be established independently of the evaluated model's response.

The model MUST NOT be used as the source of truth for its own evaluation.

### 8.2 Numerical Comparisons

Floating-point results MUST be compared using an appropriate tolerance rather than strict equality, except where exact equality is explicitly required.

The evaluation framework MUST use `math.isclose()` for numerical comparisons.

**Default tolerance:**

```python
rel_tol=1e-9
abs_tol=1e-12
```

Custom tolerances MAY be provided when justified by the test case requirements.

#### Boolean Exclusion

Before performing a numerical comparison, the evaluation framework MUST validate the types of both the actual and expected values.

Boolean values MUST NOT be accepted as valid numerical results, even though Python treats `bool` as a subclass of `int` and allows comparisons such as:

```python
True == 1.0  # True
```

The framework MUST explicitly reject Boolean values before performing numerical comparisons:

```python
if type(actual) is bool:
    raise AssertionError("Boolean result is not a valid numerical result")

if type(expected) is bool:
    raise AssertionError("Boolean expected value is not valid")
```

This validation MUST take place before calling `math.isclose()`.

#### Numerical Type Validation

Both actual and expected values MUST be integers or floating-point numbers, excluding Boolean values.

Values of other types MUST be rejected.

#### Finite Value Validation

Actual and expected numerical values MUST be finite.

The framework MUST reject:

- NaN (`float("nan")`)
- Positive infinity (`float("inf")`)
- Negative infinity (`float("-inf")`)
- Integer values that cannot be represented as finite floating-point numbers during comparison.

#### Tolerance Validation

Both `rel_tol` and `abs_tol` MUST:

- Be integers or floating-point numbers, excluding Boolean values.
- Be finite.
- Be non-negative.

The framework MUST reject invalid tolerance types with `TypeError` and negative or non-finite tolerances with `ValueError`.

Zero tolerance values MUST be accepted.

#### Validation Order

The evaluation framework MUST validate inputs in the following order:

1. Validate the actual value.
2. Validate the expected value.
3. Validate tolerance types and values.
4. Perform the numerical comparison using `math.isclose()`.

Invalid inputs MUST be rejected before the numerical comparison is performed.

#### Comparison Failure

If both numerical values and tolerances are valid, but the actual value is not sufficiently close to the expected value, the framework MUST raise `AssertionError`.

The comparison MUST use the configured relative and absolute tolerances.

### 8.3 Generated Code Evaluation

The generated implementation will be evaluated against the acceptance criteria and test cases defined in this document.

The evaluation MUST distinguish between:

- Syntax and extraction failures.
- Structural and signature failures.
- Functional failures.
- Numerical precision failures.
- Runtime and infrastructure failures.

### 8.4 Execution Safety

Generated code is untrusted input.

It MUST NOT be executed directly in the main harness process. A restricted execution environment with appropriate resource and access limitations is required before runtime evaluation.

---

## 9. Version 1.1 Scope

Version 1.1 extends the original CG-001 test case with stronger numerical and input-validation requirements.

It does not require a particular implementation strategy.

The objective is to evaluate whether an LLM can generate code that satisfies a clearly defined functional contract, including challenging edge cases and mathematical properties.
