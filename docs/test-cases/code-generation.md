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

The aggregation rules apply to individual criterion results independently of the final run verdict.

If the extracted Python source cannot be parsed into an AST because of a syntax error, AC7 is recorded as `Not Evaluated`.

If the extracted source code cannot be parsed by the applicable language parser, any structural acceptance criterion requiring successful parsing is recorded as `Not Evaluated`.

If the source code parses successfully but a required target definition is missing, the corresponding structural acceptance criterion is recorded as `Fail`.

### 3.6 Versioning and Change Control

Any change to the prompt text, a Hard acceptance criterion, test data, or comparison rules requires a new Case Version.

Documentation-only edits and changes limited to Soft criteria increment the minor version.

Results produced under different Case Versions must never be aggregated or compared as the same experiment.

A version is frozen at its first execution. Editorial changes made before any execution record exists do not require a version bump, but must be listed in the case changelog.

## 4. Test Cases

This section provides an index of test cases included in the Code Generation Test Suite.

Each test case has a separate specification document that serves as the authoritative source for its requirements, acceptance criteria, test data, validation rules, and expected outcomes.

The general evaluation methodology defined in Section 3 applies to all test cases unless a test case explicitly defines additional or different requirements.

### 4.1 Test Case Registry

| Test ID | Test Name | Programming Language | Current Version | Specification |
|---|---|---|---|---|
| CG-001 | Generate a Python Function to Calculate an Arithmetic Mean | Python | 1.2 | `docs/test-cases/CG-001_calculate_average.md` |

### 4.2 Test Case Document Authority

The individual test case specification is authoritative for all case-specific requirements.

In the event of a discrepancy between this document and an individual test case specification, the general methodology in this document applies to shared evaluation procedures, while the individual specification governs case-specific requirements.

Changes to an individual test case must follow the versioning and change-control rules defined in Section 3.6.
