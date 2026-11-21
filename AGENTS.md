# AGENTS.md

Rules for any human or AI agent working in this repository. Read before changing anything.

## What this project is
An LLM evaluation harness: datasets, a reference implementation, comparison helpers,
code extraction/validation, and immutable result models persisted to JSON.

## Frozen contracts (do not change silently)
These decisions are deliberate but not permanent. Each may be changed, but only
consciously: after discussion, with explicit approval, and with a matching test
update. Do not change any of them silently. Details live in the module docstrings.

- Status semantics: PASS / FAIL / ERROR / SKIPPED.
  `actual_exception` = outcome of the tested code; `error` = evaluation/infrastructure problem.
  ERROR requires `error` and forbids `actual_exception`; PASS/FAIL may carry `actual_exception`.
- Results are deeply immutable. `_freeze_value` allow-list: None, bool, int, float, str,
  Mapping (string keys only), list/tuple -> tuple, set/frozenset -> frozenset.
  After freezing, list and tuple are indistinguishable; the dataset is the source of truth for replay.
- Extraction: only fenced Python blocks (python/py/python3); a candidate must define the required
  function; one candidate -> it, several -> first + `ambiguous`. Unclosed fences discarded, no
  recovery. Dedent by the OPENING fence's leading spaces (never `textwrap.dedent`); tabs untouched.
- Validation: `check_syntax` returns None or exactly {error_type, message, line, column};
  uses `compile(code, "<llm_generated>", "exec")` — it never executes code.
- Serialization: strict JSON (`allow_nan=False`), `ensure_ascii=False`; NaN/Inf are tagged.
- Storage: atomic write (mkstemp in target dir + os.replace + cleanup on failure); date from
  started_at in UTC; run_id, dataset_id and task_category (when not None) are validated as
  safe path segments before any path is built. Validation rejects empty values, path separators,
  Windows-forbidden characters, control characters, Windows-reserved device names,
  leading/trailing whitespace and trailing dots. UTF-8 byte limits: task_category=200,
  dataset_id=200, run_id=150.
- Python: >=3.10 as declared in pyproject.toml. Interpreter-version support (including the
  null-byte behaviour) is part of the ongoing audit and is not frozen.

## Editing rules
- Never edit a test to make a failing test pass. If a test looks wrong, say so and get approval first.
- Never weaken an assertion without approval.
- Every behavior change needs a matching test change.
- Keep docstrings/contracts in sync with behavior.
- No new runtime third-party dependency without discussion.

## Review workflow
Every meaningful change is reviewed before commit. Full procedure: `docs/review_process.md`.
- Gates that must be green first: `ruff check .`, `ruff format --check .`, `pytest -q`.
- Build a review packet and hand it to the external reviewer (currently Qwen, via chat).
  - Manual template until the tool exists: see `docs/review_process.md`.
  - Tool when present: `python -m llm_eval.devtools.review_packet --staged`.
- Commit only after APPROVE. Reviewer feedback is decided jointly; it is not auto-applied.

## Never
- Commit `review_packet.md` or anything under `results/`.
- Bypass hooks with `--no-verify`.
- Stage partial files (`git add -p`) right before building a review packet.

## Reviewer focus
- Contract compliance against this file and module docstrings.
- Behavior changed without a test change, or a test changed without a behavior change.
- Weakened assertions.
- Path/identifier safety, JSON strictness, immutability leaks.
- Config drift (declared rules/tools/versions vs reality).
