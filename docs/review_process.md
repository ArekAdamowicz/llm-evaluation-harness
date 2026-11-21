# Review Process

## 1. Purpose

Every meaningful change must be reviewed before it is committed.

The project uses two independent quality gates:

- Automated checks: Ruff, pytest and other configured CI checks.
- External AI code review: currently performed manually with Qwen through chat.

Passing automated checks does not replace the external review. An AI review approval does not replace automated checks.

The reviewer provides findings and recommendations. It does not modify the repository or apply fixes automatically.

## 2. Review workflow

Follow these steps for every meaningful change.

### Step 1: Complete the implementation

Before starting the review:

- Finish the intended implementation.
- Add or update relevant tests.
- Update documentation and docstrings where necessary.
- Inspect the working tree and identify all files belonging to the change.
- Exclude temporary files, local notes and generated results that do not belong in the commit.

Do not begin a review while the implementation is still being actively changed.

### Step 2: Run automated quality gates

Run the following commands from the repository root:

```powershell
ruff check .
ruff format --check .
pytest -q
```

All commands must pass before proceeding.

Also inspect whitespace and conflict-marker issues:

```powershell
git diff --check
```

If any check fails, investigate and fix the underlying problem before continuing.

### Step 3: Stage complete files

Stage only the files that belong to the intended change.

Use explicit file paths:

```powershell
git add AGENTS.md
git add docs/review_process.md
```

The commands above are examples. Add the actual files belonging to the current change.

Do not use `git add .` or `git add -p`.

Inspect the staged changes:

```powershell
git status --short
git diff --cached --stat
git diff --cached
git diff --cached --check
```

Verify that:
- All intended changes are staged.
- No unrelated files are staged.
- No temporary files or generated results are included.
- The staged diff contains the complete change to be reviewed.
- No whitespace errors or conflict markers are present in the staged diff.
- The staged diff has been inspected for conflict markers.

### Step 4: Build the review packet

Until an automated packet generator exists, prepare `review_packet.md` manually.

The packet must contain:

1. **Project context** — a short description of the LLM evaluation harness.
2. **Review objective** — what the change is intended to accomplish.
3. **Relevant contracts** — applicable rules from `AGENTS.md` and module docstrings.
4. **Changed files** — a list of all staged files.
5. **Staged diff** — the complete output of `git diff --cached`.
6. **New or relevant file contents** — include complete contents when needed to understand the change.
7. **Automated checks** — commands executed and their results.
8. **Review questions** — specific concerns or areas that deserve additional attention.

Do not omit relevant changes merely to shorten the packet.

The packet is temporary and must not be committed.

When the packet generator is implemented, the intended command is:

```powershell
python -m llm_eval.devtools.review_packet --staged
```

### Step 5: Submit the packet to Qwen

Send the complete review packet to the external reviewer through chat.

Use the following instructions:

> You are an independent code reviewer for this repository.
>
> Review the supplied changes against `AGENTS.md`, relevant module docstrings, tests and the stated requirements.
>
> Do not modify files, generate replacement implementations or assume that the proposed implementation is correct.
>
> Look for:
> - Contract violations.
> - Incorrect or incomplete behavior.
> - Missing edge cases and tests.
> - Tests that do not actually verify the intended behavior.
> - Weakened assertions.
> - Regressions and unintended side effects.
> - Security issues, especially path/identifier safety.
> - JSON serialization and immutability problems.
> - Documentation and configuration inconsistencies.
>
> Classify each finding as one of:
> - `BLOCKER` — a serious correctness, security or contract issue.
> - `SHOULD-FIX` — a meaningful problem that should be corrected before approval.
> - `NIT` — a minor improvement that does not block approval.
> - `QUESTION` — something that needs clarification before a reliable conclusion can be reached.
>
> For every finding, provide:
> - The affected file and location.
> - A clear explanation of the problem.
> - Why it matters.
> - A concrete recommendation.
>
> Do not invent issues. If a concern cannot be confirmed from the supplied material, label it as a question rather than a finding.
>
> Finish with exactly one overall decision:
> - `APPROVE` — no unresolved BLOCKER or SHOULD-FIX findings.
> - `REQUEST CHANGES` — at least one unresolved BLOCKER or SHOULD-FIX finding.
>
> Be critical, precise and evidence-based.

### Step 6: Discuss and resolve findings

Review the feedback together before making changes.

- Do not automatically accept every suggestion.
- Do not automatically apply reviewer-generated code.
- Discuss findings and decide whether they represent real problems.
- Do not weaken tests or change frozen contracts merely to satisfy the reviewer.
- Apply agreed changes manually.
- Record the reasoning when a finding is intentionally rejected.

After making corrections:

1. Run the automated quality gates again.
2. Inspect the updated working tree.
3. Stage the complete updated files.
4. Build a new review packet.
5. Submit the updated packet for another review.

The previous approval does not cover changes made after that review.

### Step 7: Commit

Commit only after:

- All required automated checks pass.
- The final staged diff has been inspected.
- The external reviewer returns `APPROVE`.
- All blocking findings have been resolved or explicitly discussed and addressed.

Use a commit message describing the change.

Never bypass repository hooks with `--no-verify`.

## 3. Review packet template

Use the following structure for the temporary `review_packet.md`:

```markdown
# Code Review Packet

## 1. Project context

LLM evaluation harness.

## 2. Change objective

[Describe the intended behavior and reason for the change.]

## 3. Relevant contracts

[List applicable AGENTS.md rules and module contracts.]

## 4. Changed files

[List all staged files.]

## 5. Automated checks

- ruff check .
- ruff format --check .
- pytest -q
- git diff --check

[Include actual results.]

## 6. Review questions

[List specific concerns or questions.]

## 7. Staged diff

[Paste complete git diff --cached output.]

## 8. Additional file contents

[Include relevant complete files if the diff alone is insufficient.]
```

## 4. Files that must not be committed

- `review_packet.md`
- Anything under `results/`
- Temporary files and local artifacts unrelated to the project.

The `.gitignore` file should exclude `review_packet.md`.

## 5. Review principles

- The repository's documented contracts take precedence over assumptions.
- Every behavior change must have corresponding test coverage.
- A passing test suite is necessary but not sufficient.
- Review findings must be supported by evidence.
- Human approval is required before changes are accepted.
- No commit is made without a final `APPROVE` decision.
