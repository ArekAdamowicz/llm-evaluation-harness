# Code Generation Test Suite

## 1. Purpose

The purpose of this test suite is to evaluate an LLM's ability to generate correct, reliable, and maintainable code based on natural-language instructions, programming language requirements, and specified constraints.

The suite focuses on functional correctness, adherence to requirements, handling of edge cases, and consistency of generated code.

In the current iteration, maintainability is assessed only through a lightweight documentation rubric. Static analysis, linting, and complexity metrics are planned for later iterations and are not part of the present verdict.

The initial implementation uses Python as the first target language. Future test cases may cover other languages, including JavaScript, SQL, Java, and C#.

## 2. Scope

The Code Generation Test Suite covers:

- Generation of code that meets explicitly defined functional requirements.
- Correct handling of valid inputs and specified edge cases.
- Adherence to requested function signatures and type annotations.
- Preservation of input data when required.
- Handling of errors and exceptions according to the specification.
- Basic code structure and documentation requirements.
- Consistency of generated solutions across repeated executions.

The suite distinguishes between mandatory requirements and additional quality observations.

### 2.1 Evaluation Categories

| Category | Description | Impact on Verdict |
|---|---|---|
| Hard Requirements | Explicit functional and structural requirements that must be satisfied. | Determines Pass/Fail |
| Soft Requirements | Code quality, documentation quality, readability, and other qualitative characteristics. | Reported separately or evaluated using a defined rubric |
| Informational | Additional observations that do not directly affect the test verdict. | No impact on Pass/Fail |
Runtime availability validation is performed separately from AC7 static structural validation. A missing or non-callable module-level `calculate_average` name after successful import results in `Fail` / `wrong_signature`.

## 3. Evaluation Methodology

Each test case defines:

- A unique test case ID and version.
- A specific capability being evaluated.
- A prompt sent to the model.
- Preconditions and execution constraints.
- Explicit acceptance criteria.
- Test data with expected results.
- Validation methods.
- A defined outcome and failure classification.

### 3.1 Response Handling

The raw model response must be saved verbatim before any processing or evaluation takes place.

Extraction rules:

1. Collect fenced code blocks whose language tag is `python`, `py`, or `python3` (case-insensitive), in source order.
2. A tagged Python block is collected even if its content is invalid Python. A syntax error is an evaluation result, not an extraction failure.
3. Collect untagged fenced blocks only if their content parses as valid Python.
4. Ignore fenced blocks tagged with any other language.
5. Concatenate all collected blocks in source order into a single module, separating consecutive blocks with two newline characters.
6. If the target function is defined multiple times, the last top-level definition takes effect, following normal Python execution semantics.
7. If no blocks were collected, the entire response may be treated as source code only if it parses as valid Python.
8. If no identifiable Python source code is available, the run is `Fail` with category `no_code`.
9. If the model requests clarification and provides no usable implementation, the run is `Blocked` with category `clarification_requested`.
10. If the model explicitly declines to produce the requested code, the run is `Blocked` with category `refusal` and is flagged for review.
11. If a response contains both a clarification question and a usable implementation, the implementation is evaluated normally.
12. Explanatory prose outside code blocks is ignored during functional evaluation.

Constraints on the tester:

- Generated code must not be manually edited, repaired, completed, or reformatted before evaluation. Any such modification invalidates the original evaluation run.
- Every generation is a separate run.
- Regenerating a response or retrying after a failure creates a new Run ID.
- A previous response is never overwritten or discarded.
- Selecting the best answer after several regenerations invalidates the measurement.

The evaluation record must include the number of collected code blocks, the extraction strategy applied, and any blocks that were ignored.

### 3.2 Run Statuses

The following statuses are used for individual execution runs:

| Status | Definition |
|---|---|
| Pass | All mandatory acceptance criteria have been satisfied. |
| Fail | At least one mandatory acceptance criterion has failed or could not be evaluated because of the generated response or code. |
| Blocked | No usable implementation was evaluated, or execution was withheld after a safety review. Examples include clarification requested, refusal, unsafe code, or no response artifact available. |
| Error | The evaluation process itself failed due to an infrastructure, configuration, or unexpected harness problem. This is not a judgement of the model. |

`Not Executed` is a tracking state used when no execution record exists. It is not a completed run result.

### 3.3 Outcome Categories

Each outcome category maps to exactly one run status.

| Category | Run Status | Description |
|---|---|---|
| `no_code` | Fail | No identifiable Python source code was provided. |
| `syntax_error` | Fail | Generated source code contains invalid Python syntax. |
| `import_error` | Fail | Module-level execution or required imports failed. |
| `wrong_signature` | Fail | Function name, parameters, or annotations do not meet the specification. Determined by static source inspection. |
| `wrong_value` | Fail | The returned result is incorrect, non-numeric, boolean, NaN, infinite, or has an incorrect runtime type. |
| `wrong_exception_type` | Fail | For test data that specifies an expected exception: an exception of the wrong type is raised, or no exception is raised at all. |
| `wrong_exception_message` | Fail | For test data that specifies an expected exception: the exception message does not match the specification exactly. |
| `unexpected_exception` | Fail | An exception is raised during a test invocation for which no exception is expected. The exception type and traceback are recorded. |
| `input_mutated` | Fail | The function modifies the original input data. |
| `timeout` | Fail | Generated code exceeds the configured execution budget. The execution phase is recorded. |
| `clarification_requested` | Blocked | The model requests clarification instead of providing a solution. |
| `refusal` | Blocked | The model explicitly declines to produce the requested code. Flag for review. |
| `missing_response` | Blocked | No response artifact is available and no infrastructure failure is known. | `missing_response` applies only when no response artifact is available. An existing response artifact containing an empty response or no identifiable Python source code is classified as `no_code`, not `missing_response`.

A response containing only whitespace or an empty message body is therefore classified as `no_code`, provided the response artifact exists and no provider or infrastructure failure is known.
| `unsafe_code_skipped` | Blocked | Execution was withheld after a pre-execution safety review. The reason and reviewer are recorded. |
| `environment_error` | Error | Harness, interpreter, or configuration failure. |

A single run may produce several outcome categories. The report must preserve individual acceptance criterion results rather than recording only one category.

A run-level `Blocked` or `Error` outcome determines the run verdict in accordance with Section 3.5. Static acceptance criteria may still be evaluated and may have individual `Fail` results even when the overall run verdict is `Blocked` or `Error`.

### 3.4 Classification Precedence

Classification precedence is applied in order to the pre-execution phase:

1. No response artifact exists: `missing_response`, unless a provider or infrastructure failure is known, in which case the run is `Error` / `environment_error`.
2. An explicit refusal with no usable implementation: `refusal`.
3. A clarification request with no usable implementation: `clarification_requested`.
4. A collected tagged Python block contains invalid syntax: `syntax_error`.
5. No identifiable Python source code is available: `no_code`.
6. Python source was collected but execution was withheld after a safety review: `unsafe_code_skipped`.

A safety review is performed only when Python source code has been collected. It does not apply when there is no usable source code to review.

Post-extraction categories (`import_error`, `wrong_signature`, `wrong_value`, `wrong_exception_type`, `wrong_exception_message`, `unexpected_exception`, `input_mutated`, `timeout`) are recorded in addition to, not instead of, the pre-execution categories, where applicable. A run may carry several of them.

`wrong_signature` is determined by static inspection and does not require execution.

A tagged Python code block containing invalid Python syntax is classified as `syntax_error`.

An untagged code block containing invalid Python syntax is not collected as Python code and therefore results in `no_code`, unless another valid Python implementation is found in the response.

This distinction follows from the extraction rules and is intentional.

### 3.5 Acceptance Criterion States and Run Verdict

Each acceptance criterion is recorded as `Pass`, `Fail`, or `Not Evaluated`.

`Not Evaluated` applies when a criterion could not be exercised, for example:

- No usable implementation was produced.
- The module failed to import.
- Execution timed out before the criterion could be tested.
- The target function was never callable.
- Execution was withheld after a safety review.

Static and dynamic criteria:

- Structural and documentation criteria are static checks based on source inspection. They may be evaluated without executing the generated code, including when execution was withheld after a safety review.
- All other criteria are dynamic and require execution. When execution does not take place, they are recorded as `Not Evaluated`.

Run verdict derivation:

1. If a `Blocked` category applies, the run verdict is `Blocked`.
2. Otherwise, if an `Error` category applies, the run verdict is `Error`.
3. Otherwise, if any Hard criterion is `Fail` or `Not Evaluated`, the run verdict is `Fail`.
4. Otherwise, the run verdict is `Pass`.

A criterion that has actually been exercised and failed must remain `Fail`, even if a different criterion could not be evaluated.

`Not Evaluated` must never be silently reported as `Pass`.

Soft criteria that could not be exercised are recorded as `Not Evaluated` and do not affect the run verdict.

A `Blocked` or `Error` run verdict takes precedence over the ordinary Hard-criterion verdict. This does not erase individual criterion results: static criteria may still be reported as `Fail` in a `Blocked` or `Error` run.

#### 3.5.1 Acceptance Criterion Aggregation Rules

Each acceptance criterion may be associated with one or more test data items or validation checks.

A Hard acceptance criterion receives `Pass` only when all applicable checks associated with that criterion pass.

If at least one applicable check fails, the criterion receives `Fail`, even if other checks associated with it pass or could not be evaluated.

If no applicable check fails but at least one required check could not be evaluated, the criterion receives `Not Evaluated`.

A criterion receives `Pass` only when all required checks have been successfully evaluated and passed.

For AC6, all applicable test data items TD1-TD10 must pass the input mutation check.

For AC7, all structural requirements defined in Section 4.6 must pass.

For AC8, the rubric score and threshold defined in Section 4.7 determine the criterion result.

The aggregation rules apply to individual criterion results independently of the final run verdict.

If the extracted Python source cannot be parsed into an AST because of a syntax error, AC7 is recorded as `Not Evaluated`.

If the source parses successfully but no qualifying top-level `calculate_average` function definition is found, AC7 is recorded as `Fail`.

If the target function is found but one or more structural requirements are violated, AC7 is recorded as `Fail`.

### 3.6 Versioning and Change Control

Any change to the prompt text, a Hard acceptance criterion, test data, or comparison rules requires a new Case Version.

Documentation-only edits and changes limited to Soft criteria increment the minor version.

Results produced under different Case Versions must never be aggregated or compared as the same experiment.

A version is frozen at its first execution. Editorial changes made before any execution record exists do not require a version bump, but must be listed in the case changelog.

## 4. Test Cases

### CG-001: Generate a Python Function to Calculate an Arithmetic Mean

#### 4.1 Test Information

| Field | Value |
|---|---|
| Test ID | CG-001 |
| Test Name | Generate a Python Function to Calculate an Arithmetic Mean |
| Capability | Code Generation |
| Programming Language | Python |
| Difficulty | Easy |
| Priority | High |
| Case Version | 1.0 |
| Last Updated | 2026-11-17 |
| Test Type | Functional / Structural |
| Evaluation | Behavioural validation against predefined test data; AC8 scored with a rubric. Execution mode (manual or automated) is recorded per run. |

#### 4.2 Objective

Verify that the LLM can generate a Python function that calculates the arithmetic mean of a list of numbers and follows all explicitly defined functional and structural requirements.

The test evaluates:

- Correct calculation of the arithmetic mean.
- Handling of positive, negative, zero, and integer inputs.
- Correct handling of an empty list.
- Correct exception type and message.
- Preservation of the original input list.
- Compliance with the requested function signature and type annotations.
- Presence and basic quality of a descriptive docstring.

#### 4.3 Preconditions and Execution Budget

Before executing the test, verify the following:

1. The selected model is available and can generate responses.
2. Python 3.10 or newer is available in the evaluation environment.
3. The prompt is sent in a fresh conversation without additional user-provided context.
4. Tool usage, browsing, code execution features, and other relevant provider settings are disabled where possible or explicitly recorded.
5. Test data and expected results are not visible to the model.
6. The prompt and test case version are frozen for the duration of the evaluation.

Provider-specific or hidden system instructions may not be directly observable. Any known provider configuration must therefore be recorded as execution metadata, and unknown configuration must be recorded as `unknown`.

Execution budget:

| Phase | Budget |
|---|---|
| Module import and top-level execution | 5 seconds |
| Each function invocation | 5 seconds |
| Total per run | 60 seconds |

The 60-second total run budget is the absolute upper limit for the complete evaluation run. It includes module import, all function invocations, subprocess startup overhead, inter-process communication, and evaluation-related execution overhead.

If the total run budget is exceeded, the run is classified as `Fail` with category `timeout`, unless an infrastructure failure is responsible, in which case the run is classified as `Error` with category `environment_error`.

Exceeding any budget is recorded as `Fail` / `timeout`, with the phase noted.

The import budget exists because generated code may hang at module level, before any function is called.

Execution security:

Generated code must be treated as untrusted input.

- Generated code must not be executed directly inside the harness process.
- Code execution must take place in a separate process with a timeout.
- The execution environment should not expose API keys, credentials, personal files, or other sensitive data.
- Network access and filesystem access should be restricted where possible.
- CPU and memory limits should be applied where supported.
- The harness must capture standard output, standard error, exit status, and timeout information.

A subprocess and timeout alone do not constitute a secure sandbox. They provide process separation and execution control, but do not guarantee protection against malicious code.

A stronger isolation mechanism, such as a restricted container or dedicated sandbox, is planned for a later implementation stage.

Until stronger isolation is available, generated code must undergo a manual safety review before execution.

Execution must be withheld if the code attempts or appears to require:

- Network access.
- Writing outside the designated working directory.
- Spawning additional processes.
- Accessing credentials or sensitive environment variables.

If execution is withheld, the outcome is classified as `unsafe_code_skipped` and the run status is `Blocked`.

The reason for withholding execution and the reviewer identifier must be recorded in the run metadata.

The safety review is a preliminary risk check, not a guarantee that code is safe. The absence of obvious unsafe operations does not make subprocess execution a secure sandbox.

#### 4.4 Prompt

| Field | Value |
|---|---|
| Prompt Version | 1.0 |
| Prompt File | `docs/test-cases/prompts/CG-001_v1.0.txt` |
| Prompt Hash (SHA-256) | 5745e51818f44ca7eb8f0735c2f3d79425ade0e4716b6ca06a1d67905c41c599 |

The prompt file is the single source of truth. The prompt text is not duplicated in this document, to avoid drift between copies.

Line breaks, punctuation, and spacing inside the prompt file are part of the prompt. The prompt must be sent verbatim, with no added user context. Any provider-specific system instructions that cannot be controlled must be recorded as `unknown`, or documented where observable.

The prompt artifact is generated using `scripts/generate_cg001_prompt.py`. Run the script from the repository root:

```bash
python scripts/generate_cg001_prompt.py
```

The script writes the prompt file using UTF-8 without BOM, LF line endings, and exactly one trailing newline. It then calculates and prints the SHA-256 hash of the actual file bytes.

After running the script:

1. Verify that the generated prompt file contains the intended prompt.
2. Copy the SHA-256 value printed by the script into the table above.
3. Record the same hash in the execution metadata.

The prompt file is authoritative and the hash is derived metadata. If the computed value differs from a previously recorded value, first verify that the file content is the intended prompt, then update the recorded hash. Never adjust the file bytes to match a previously recorded hash.

The hash must be computed and recorded before the first execution.

#### 4.5 Acceptance Criteria

##### Hard Requirements

| ID | Acceptance Criterion | Validation Method |
|---|---|---|
| AC1 | The function correctly calculates the arithmetic mean for positive floating-point inputs and returns a float. | Execute predefined test data, compare actual and expected results, and verify runtime type. |
| AC2 | The function correctly handles negative numbers and zero and returns a float. | Execute predefined test data, compare actual and expected results, and verify runtime type. |
| AC3 | The function correctly handles integer inputs and returns the arithmetic mean as a float. | Execute predefined test data, compare the result, and verify runtime type. |
| AC4 | An empty input list raises a ValueError. | Execute the function with an empty list and verify the exception type. |
| AC5 | The exception message for an empty input list is exactly "numbers must not be empty", provided the expected ValueError is raised. | Compare the actual exception message with the expected string only when the exception type is ValueError. If a different exception type is raised or no exception is raised, AC5 is recorded as Not Evaluated. |
| AC6 | The function does not modify the original input list, regardless of whether the function returns a result or raises an exception. | Compare the original input with a deep copy after execution. |
| AC7 | The generated function follows the required name, parameter structure, and type annotations. | Inspect the generated source using AST-based structural validation. |

AC7 evaluates compliance with the required function interface and type semantics. Equivalent annotation representations are accepted according to the explicit whitelist defined in Section 4.6. The criterion evaluates semantic equivalence within this whitelist rather than requiring identical source-level spelling.

##### Soft Requirements

| ID | Acceptance Criterion | Validation Method |
|---|---|---|
| AC8 | The function contains a descriptive and relevant docstring. | Evaluate using the defined three-point rubric. |

AC7 and AC8 are static criteria and may be evaluated without executing the generated code, as described in Section 3.5.

#### 4.6 Detailed Structural Requirements for AC7

Validation target:

- Structural validation targets the last top-level `def calculate_average` in the extracted module, matching the definition that takes effect at runtime.
- Helper functions and other module-level code are not constrained by AC7.
- A lambda assignment, a nested function, or a method does not satisfy AC7.

The target function must satisfy all of the following conditions:

- Function name must be exactly `calculate_average`.
- It must be a regular function, not an asynchronous function.
- It must have exactly one parameter.
- The parameter name must be `numbers`.
- The parameter must be a required positional parameter.
- No additional positional, keyword-only, or variadic parameters are allowed.
- The parameter must not have a default value.
- A positional-only marker (`/`) is accepted. The harness always calls the function positionally.
- The parameter annotation must be one of the following:
  - `list[float]`
  - `List[float]`
  - `typing.List[float]`
- The return annotation must be `float` or `builtins.float`.

Annotation normalization:

- Annotation comparison is performed using a normalized AST representation.
- Whitespace and redundant parentheses are ignored. For example, `list[ float ]` is equivalent to `list[float]`.
- String annotations are accepted if their parsed content matches the whitelist, for example `numbers: "list[float]"`.
- An annotation string must parse as a valid expression and match one of the accepted forms exactly after normalization.
- String annotations are parsed as annotation expressions and checked against the same annotation whitelist.
- When an annotation is explicitly provided as a string literal, the referenced type does not need to be available at runtime. This allows valid string annotations such as `"List[float]"` without requiring `from __future__ import annotations`.
- Annotations that use expressions outside the whitelist are rejected.

Import requirements:

- Imports must appear at module top level.
- If the annotation uses `List`, the module must contain a corresponding import: `from typing import List`.
- If the annotation uses `typing.List`, the module must contain `import typing`.
- If the annotation uses `builtins.float`, the module must contain `import builtins`.
- Import aliases are not accepted in this test case.
- An import inside the target function is not accepted.
- An import inside a top-level `if TYPE_CHECKING:` block is accepted when either `from __future__ import annotations` is present, or the annotation is a string literal.
- The `TYPE_CHECKING` condition must be recognizable as `TYPE_CHECKING` or `typing.TYPE_CHECKING`, with the corresponding import available.
- For non-string annotations using names imported only under `TYPE_CHECKING`, `from __future__ import annotations` is required.
- The required import must bind the referenced name to the expected standard-library typing object. Imports from unrelated modules do not satisfy this requirement.

The use of `from __future__ import annotations` is permitted. Structural validation must inspect annotation expressions via AST rather than relying exclusively on runtime annotation evaluation.

The following alternatives are not accepted:

- Missing parameter or return annotations.
- `Any`.
- `Sequence[float]`.
- `Iterable[float]`.
- `list[int | float]`.
- A keyword-only `numbers` parameter.
- Additional required parameters.
- Asynchronous function definitions.

Rationale: the prompt specifies an exact function interface. The accepted annotation representations are explicitly defined by the whitelist above. A wider annotation may be better engineering practice, but it deviates from the requirements of this test case. AC7 is an instruction-adherence criterion, not a code-quality judgement.

These restrictions apply specifically to this test case. Other test cases may evaluate different signature and typing requirements.

##### 4.6.1 Runtime Availability

Static AST validation identifies the last top-level `def calculate_average` definition in the extracted module.

Dynamic validation must additionally verify that, after successful module import, the module-level name `calculate_average` refers to a callable object.

If the name is missing or is not callable after import, the run is classified as `Fail` with category `wrong_signature`.

This runtime check is separate from AC7 static structural validation.

#### 4.7 Docstring Evaluation Rubric for AC8

The docstring is evaluated using three independent criteria.

| Criterion | Points | Description |
|---|---:|---|
| Non-empty documentation | 1 | The function contains a non-empty docstring that is not merely a placeholder. |
| Purpose | 1 | The docstring explains that the function calculates or returns the arithmetic mean or average. |
| Empty-input behavior | 1 | The docstring documents that an empty input list raises `ValueError`. |

Examples of placeholder docstrings that do not satisfy the non-empty documentation criterion include:

- `"""TODO."""`
- `"""Function."""`
- `"""Calculate."""`

A docstring must contain meaningful information about the function rather than only a generic label or placeholder.

The rater should apply this rule consistently across all evaluation runs.

**Passing threshold: at least 2 out of 3 points.**

The achieved score must always be recorded, even when the criterion passes.

Points 1 and 2 reflect the explicit instruction to include a descriptive docstring. Point 3 is a bonus expectation, not an explicit requirement of the prompt.

When AC8 is scored by a human, the rater identifier must be recorded. If the target function cannot be located, AC8 is `Not Evaluated`.

This is a lightweight documentation-quality check, not a comprehensive assessment of documentation quality.

#### 4.8 Test Data

The following test data must be used to validate the generated function.

| Test Data ID | Input | Expected Result | Acceptance Criteria |
|---|---|---|---|
| TD1 | `[1.0, 2.0, 3.0]` | `2.0` | AC1, AC6 |
| TD2 | `[2.5]` | `2.5` | AC1, AC6 |
| TD3 | `[0.1, 0.2]` | `0.15` | AC1, AC6 |
| TD4 | `[10.0, 10.0, 10.0]` | `10.0` | AC1, AC6 |
| TD5 | `[-2.5, -7.5]` | `-5.0` | AC2, AC6 |
| TD6 | `[-1.0, 0.0, 1.0]` | `0.0` | AC2, AC6 |
| TD7 | `[0.0, 0.0]` | `0.0` | AC2, AC6 |
| TD8 | `[1, 2]` | `1.5` | AC3, AC6 |
| TD9 | `[]` | Raise `ValueError` with exact message `"numbers must not be empty"` | AC4, AC5, AC6 |
| TD10 | `[1, 2, 3]` | `2.0` | AC3, AC6 |

All value-returning test data (TD1-TD8, TD10) requires a runtime result of type `float`. TD9 requires an exception and has no return value.

Integer inputs are deliberately included even though the requested parameter annotation is `list[float]`. Python does not enforce type annotations at runtime, and under the PEP 484 numeric tower an `int` is acceptable where `float` is declared. Integer values are therefore valid inputs for this test.

TD10 is the discriminating case for the float-return requirement: an integer-valued mean of integer inputs is a situation where an implementation may otherwise return an `int`.

#### 4.9 Numerical Comparison Rules

Floating-point results must not be compared using strict equality.

The following comparison rule must be used:

```python
math.isclose(
    actual,
    expected,
    rel_tol=1e-9,
    abs_tol=1e-12
)
```

The comparison is equivalent to:

```text
abs(actual - expected) <= max(
    rel_tol * max(abs(actual), abs(expected)),
    abs_tol
)
```

Both relative and absolute tolerances are required. The absolute tolerance is essential when the expected result is zero, where relative tolerance alone can never pass.

Type and value validation, applied before the tolerance check:

1. Reject `bool` explicitly. `math.isclose(True, 1.0)` returns `True`, so the tolerance check alone does not exclude booleans.
2. Accept only `int` and `float` as numeric candidates. Any other type, including `Decimal`, `Fraction`, `str`, and `None`, is rejected here.
3. Reject `NaN` and infinite results.
4. Require `isinstance(actual, float)` for TD1-TD8 and TD10, as explicitly requested by the prompt. Float subclasses are accepted. An `int` result passes step 2 but fails here; this is the intended behaviour.
5. Compare the returned value against the expected result using the defined tolerance.

Any violation of these rules results in `Fail` / `wrong_value`.

These rules concern returned values for the defined test data TD1-TD10 only. NaN and infinite inputs remain out of scope, as described in Section 4.12.

#### 4.10 Input Mutation Validation

The original input list must remain unchanged after function execution.

For each test invocation:

1. Create a deep copy of the input list.
2. Execute the generated function.
3. Compare the original input list with the saved copy.
4. Repeat the comparison even if the function raises an exception.

The comparison must take place in a `finally` block or an equivalent mechanism that guarantees validation after both successful and unsuccessful execution.

Any difference in list contents, element order, or length results in failure of AC6.

AC6 applies to every test data item, including the empty-list exception path in TD9.

If execution is terminated by an external timeout before the function invocation completes, AC6 is recorded as `Not Evaluated` unless the input mutation state can be reliably retrieved from the execution process.

A forced process termination does not guarantee execution of the function's `finally` block. Therefore, the harness must not assume that post-execution mutation validation has taken place after a forced timeout.

#### 4.11 Allowed Implementation Approaches

The test evaluates the generated function's behavior and compliance with the specification, not a particular algorithm.

The following implementation approaches are acceptable:

- Using Python's built-in `sum()` and `len()`.
- Using `statistics.mean`, provided the returned value is a `float`. Note that `statistics.mean([1, 2, 3])` returns `2`, an integer. Because the prompt explicitly requires a float result, such an implementation must convert the result with `float(...)` to satisfy AC3 on TD10.
- Using `statistics.fmean`, which returns a float.
- Using `math.fsum` with division.
- Using loops or comprehensions.
- Using helper functions.
- Using appropriate Python standard-library imports.

No specific algorithm or implementation strategy is required.

An implementation must not be rejected solely because it uses a different valid approach from the expected implementation. It may only be rejected for violating a stated requirement.

Additional restrictions, such as banning particular imports or requiring a specific algorithm, should be introduced only in separate test cases where they are explicitly stated in the prompt.

#### 4.12 Additional Robustness Observations

The following inputs and behaviors are outside the mandatory scope of CG-001:

- `NaN` and positive or negative infinity as input values.
- Extremely large numbers and potential numerical overflow.
- Strings, `None`, or mixed-type lists.
- Non-list input objects.
- Custom numeric types.
- Performance under very large input sizes.

These cases may be explored as additional robustness tests, but their results must not affect the CG-001 verdict unless a future version explicitly includes them in the requirements.

#### 4.13 Execution Metadata

Each evaluation run must record enough information to make the results reproducible and comparable.

##### Required fields

| Metadata Field | Description |
|---|---|
| Run ID | Unique identifier for the individual execution. |
| Test Case ID | Identifier of the evaluated test case. |
| Test Case Version | Version of the test case specification. |
| Prompt Version | Version of the prompt used. |
| Prompt Hash | SHA-256 of the exact prompt sent to the model. |
| Execution Date | Date and time of execution, in UTC. |
| Provider | Model provider or platform. |
| Model Name | Exact model name. |
| Model Version / Snapshot | Model version or snapshot, or `unknown`. |
| Evaluation Mode | Manual or automated. |
| Generation Attempt | Index of the generation. `1` for a fresh conversation. |
| Context State | `fresh` or `regenerated_in_thread`. |
| Tool Configuration | Whether browsing, code execution, or other tools were enabled, or `unknown`. |
| Python Version | Python version used for code execution. |
| Raw Response | Original, unmodified model response or a reference to its stored artifact. |
| Extracted Code | Extracted source code or a reference to its stored artifact. |
| Code Block Count | Number of collected code blocks and the extraction strategy applied. |
| Run Status | Pass / Fail / Blocked / Error. |
| Acceptance Criterion Results | Per-criterion Pass / Fail / Not Evaluated for AC1-AC7. |
| AC8 Score | Rubric score 0-3 and Pass / Fail / Not Evaluated. |
| Rater | Identifier of the person scoring AC8. |
| Safety Review Notes | Required when execution is withheld: reason and reviewer. Otherwise `n/a`. |
| Outcome Categories | All applicable categories, not only the first one. |
| Execution Duration | Time required to execute the generated code, per phase where available. |

##### Optional fields

| Metadata Field | Description |
|---|---|
| Temperature | Sampling temperature, if configurable. |
| Top-p | Nucleus sampling value, if configurable. |
| Seed | Random seed, if supported by the provider. |
| Environment | Additional execution environment details. |
| Token Usage | Input and output token counts, if available. |
| Estimated Cost | Estimated cost of the model call, if available. |
| Provider Request ID | Provider-side identifier, if exposed. |

Unavailable metadata must be recorded as `unavailable` or `unknown` rather than silently omitted.

Regeneration rule: every generation is a separate run. Regenerating a response, retrying after a failure, or editing the prompt creates a new Run ID. A previous response is never overwritten or discarded. Selecting the best answer after several regenerations invalidates the measurement.

A regeneration inside an existing thread violates the fresh-conversation precondition. Such runs are recorded with Context State `regenerated_in_thread` and are excluded from the primary pass rate. They may be reported separately as exploratory observations.

The preferred procedure is one fresh conversation per run, in which case Generation Attempt is always `1` and Context State is `fresh`.

#### 4.14 Expected Outcome

The run verdict is derived according to Section 3.5.

The run passes when all Hard acceptance criteria AC1-AC7 pass and no Blocked or Error category applies.

AC8 is reported separately as a soft requirement. Its score must be included in the evaluation report but does not determine the hard verdict.

All applicable outcome categories must be recorded.

#### 4.15 Evaluation Notes

A single execution provides a smoke-test result, not a reliable estimate of model consistency or overall capability.

For consistency and reliability analysis, the same test case should be executed multiple times under controlled conditions. The initial target is 10-20 independent runs per model and configuration.

Repeated executions should be analyzed separately from individual test verdicts.

For future model comparisons:

- Use the same test case versions and prompt text.
- Keep provider settings as consistent as possible.
- Record any differences in model configuration.
- Report pass rates and confidence intervals.
- Consider suitable statistical tests when comparing models, taking into account whether observations are independent or meaningfully paired.
- Exclude `regenerated_in_thread` runs from the primary pass-rate calculation.

With 10-20 runs, confidence intervals are wide. Avoid ranking models on small differences in pass rate.

A temperature setting of zero does not guarantee perfectly deterministic output across all providers or model versions.

Although AC3 gives this case some discriminating power, it remains a single narrow task. The test case should be treated as one component of a broader evaluation suite, not as a standalone benchmark of code-generation capability.

#### 4.16 Changelog

| Case Version | Date | Change |
|---|---|---|
| 1.0 | 2026-11-17 | Initial release candidate. Added response extraction rules, run statuses, outcome categories, classification precedence, criterion states, verdict derivation, versioning rules, execution budgets, and execution security requirements. Clarified float return type validation and structural annotation rules. Added unexpected exception classification, context state tracking, and safety review outcomes. Prompt stored as a separate versioned artifact; prompt hash must be computed and recorded before the first execution. Version will be frozen at the first execution. No execution records exist yet. |
| 1.0 | 2026-11-17 | Clarified acceptance criterion aggregation, exception validation dependencies, equivalent annotation representations, syntax-error handling for AC7, runtime function availability, missing response classification, docstring placeholder examples, input mutation validation after timeouts, and total execution budget semantics. |
