# Copilot Instructions & Rules


## General Principles

- **Python Version**: Use features compatible with the project's declared Python version (check `pyproject.toml` or equivalent).
- **Code Style**: Follow PEP 8 and a mainstream style guide (e.g., Google). Defer to repository-specific linter/formatter configs if present.
- **Readability First**: Prioritize clear, maintainable code over premature optimization.
- **Documentation**: Add concise docstrings to public modules, classes, and functions using a consistent style (always NumPy style).
- **Type Hints**: Use type annotations for where possible.
- **Imports**: Prefer relative imports within the project; group and order imports logically.
- **Error Handling**: Use exceptions appropriately; avoid bare excepts.

---

## Repository Discovery

Before proposing changes, always:

- Inspect project metadata (`pyproject.toml`, etc.) for:
  - Python version
  - Task runner definitions (e.g., pixi)
  - Lint/format/test tool configuration
- Check for:
  - Test and source layout (`src/`, `tests/`)
  - Documentation (`README.md`, `docs/`)
  - Examples (`notebooks/`)

---

## Agentic Workflow

1. **Analyze**: Read related code, tests, and configs.
2. **Implement**: Make minimal, modular changes in `src/` and update/add tests in `tests/`.
3. **Format**: Run the repository's configured formatter via the preferred task runner.
4. **Lint**: Run the linter with autofix if supported; resolve diagnostics.
5. **Test**: Execute the test suite using the repo's standard command.
6. **Package/Sync**: Build or sync artifacts if tasks are defined.
7. **Iterate**: On failure, loop back to implementation and fix.

---

## Task Runner Selection

- Prefer project-defined tasks (from `pyproject.toml`, etc.) for formatting, linting, testing, and hooks.
- If not defined, use direct tool invocations as configured in the repo.

---

## Coding Standards

- Use pathlib for file paths.
- Keep functions small and cohesive.
- Use descriptive names and explicit returns.
- Limit side effects; keep CLI and I/O at boundaries.
- Extend existing logging patterns (avoid print for logs).
- you must also check `.github/coding-instructions.md` for coding guidelines.
---

## Testing

- Place tests in `tests/`, mirroring the source structure.
- Add unit and regression tests for new/fixed behavior.
- Respect repository markers and strictness settings.
- Keep tests deterministic and avoid flakiness.
- you must also check `.github/testing-instructions.md` for testing guidelines.

---

## Documentation & Examples

- Update `README.md` or `docs/` for public changes.
- Add runnable examples in `notebooks/` when helpful.
- Keep code snippets consistent with formatting rules.

---

## CLI & Entry Points

- Discover CLI entry points in project metadata.
- Ensure help text, options, and error messages are consistent and tested.

---

## Pre-commit & CI

- Run all pre-commit hooks before proposing commit-ready changes.
- Align local checks with CI by using the same commands as in CI configs.

---

## Safety & Constraints

- Do not introduce new tools/frameworks unless requested.
- Do not weaken lint/test strictness without clear justification.
- Prefer incremental, reviewable changes.

---

## Change Acceptance Criteria

- Code follows formatting and lint rules.
- Tests are updated and pass locally.
- Documentation is consistent with changes.

---

## Repository-specific Overrides

- If more specific instructions or tasks exist, those take precedence over these generic rules.
