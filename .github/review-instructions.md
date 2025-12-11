# Python Review Instructions

These guidelines define how to review Python code and tests in this repository to ensure compliance with project coding and testing conventions.

---

## Source of Truth

- Treat the following as the authoritative sources for conventions and rules:
  - `.github/instructions/code.instructions.md`
  - `.github/instructions/testing.instructions.md`
- Before commenting, read relevant sections in these files and use them as your review checklist.
- If these instructions conflict with generic habits or preferences, **the repository instructions take precedence**.

---

## Pre-Review Preparation

Before reviewing, gather context:

- Examine all changed files (code and tests) in the diff.
- Review `.github/instructions/code.instructions.md` for coding conventions.
- Review `.github/instructions/testing.instructions.md` for testing conventions.
- Check any additional repository instructions referenced from those files (tooling, runners, patterns).
- Do not rely solely on personal preference; verify strictly against the project’s explicit definitions.

---

## Core Review Goals

During review, confirm that changes:

- Follow the project’s Python coding conventions (style, imports, typing, structure).
- Follow the project’s testing conventions (pytest usage, fixtures, parametrization, organization).
- Respect the project’s tooling and workflow (e.g., `pixi` tasks, linting, formatting, test execution).
- Maintain or improve readability, maintainability, and testability.

If a change violates any defined convention, call it out with a concrete suggestion.

---

## Review Workflow

Follow this structured workflow for each review:

1. **Understand Intent**
   - Read the change description, commit messages, or PR summary.
   - Identify if the change is a bug fix, new feature, refactor, or test-only, and adjust scrutiny accordingly.

2. **Check Coding Conventions**
   - Compare implementation against `.github/instructions/code.instructions.md`.
   - Verify style, imports, typing, documentation, and modern Python usage.
   - Flag deviations from documented rules (type hints, module structure, path handling, docstrings).

3. **Check Testing Conventions**
   - Ensure tests follow `.github/instructions/testing.instructions.md`:
     - Use `pytest` (no `unittest`).
     - Use fixtures, parametrization, and the required module layout.
   - Check that new/changed behavior is fully tested, including branches, edge cases, and errors.

4. **Check Tooling and Workflow**
   - Confirm consistency with configured tools (formatter, linter, type checker) and project configuration.
   - Point out missing formatting, linting, or test updates that would be caught by standard project commands (e.g., `pixi` tasks).

5. **Summarize and Suggest**
   - Provide focused, actionable comments that reference the violated guideline or instruction (e.g., “This violates the docstring requirement in code.instructions.md, please add a NumPy-style docstring with examples.”).
   - Prefer concrete code suggestions over general feedback.

---

## Specific Checks: Code

- **Typing and Imports**
  - Types are present and follow the patterns in the code instructions (modern syntax, no quoted annotations, proper use of abstract base classes).
  - Imports are grouped and ordered as specified; paths use recommended modules (e.g., `pathlib`).

- **Documentation**
  - Public APIs have required NumPy-style docstrings (with examples and notes where required).
  - Internal/helper functions use concise documentation as defined.

- **Style and Design**
  - Code adheres to structural rules (modern features, function size, separation of concerns) without unnecessary complexity.

Only request changes for clear mismatches with documented conventions or significant readability/maintainability issues.

---

## Specific Checks: Tests

- **Framework and Structure**
  - Tests use `pytest` and the project’s test patterns; no `unittest` classes or mixed styles.
  - Each test module has a module-level docstring explaining its scope.
  - Fixtures, parametrization, and structure match the testing instructions.

- **Coverage and Behavior**
  - Tests cover new/changed behavior, including normal and edge cases, branches, and error paths.
  - Given–when–then mindset is reflected in test naming, comments, or docstrings.

- **Clarity and Isolation**
  - Fixtures are used for reusable setup/teardown.
  - Mocking and monkey-patching use approved tools (`pytest-mock`, `monkeypatch`), not ad-hoc/mixed approaches.

If tests are missing, incomplete, or misaligned, explicitly request additions or corrections.

---

## Decision Rules

- Approve changes only if they comply with code and testing instructions, or if deviations are justified and acceptable.
- If a rule is ambiguous, mention the ambiguity and default to the most conservative, quality-preserving interpretation.
- If reconciliation with conventions is not possible, request clarification or adjustment—do not silently accept deviations.
