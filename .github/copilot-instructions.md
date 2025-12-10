# Copilot Instructions & Rules

This file tells you how to work in this repository. Follow these instructions strictly when generating code, tests, or documentation or when assisting with any other development tasks.

---

## 1. Repository Context & Preparation

- **Read context files first:**
  - `README.md`
  - `pyproject.toml` (project config, dependencies, tools, tasks)
  - `.github/instructions/code.instructions.md` (coding standards)
  - `.github/instructions/testing.instructions.md` (testing standards)
  - `.github/workflows/` (CI context)
- **Always follow repository-specific instructions over general best practices.**

---

## 2. Core Workflow & Pixi Tasks

All development tasks must use `pixi`. **Do not run tools (pytest, black, flake8, python) directly.**

- **List tasks:** `pixi run`
- **Format & Lint:** `pixi run format` then `pixi run lint`
- **Test:** `pixi run test` (or `pixi run test <pytest-args>`)
- **Run Code:** `pixi run python <file>` or `pixi run python -c "<code>"`

**After modifying code:**
1. Run `pixi run format`
2. Run `pixi run lint`
3. Run `pixi run test`
4. If a task fails repeatedly, stop and request guidance.

---

## 3. Coding & Testing Standards

- **Code:** Follow `.github/instructions/code.instructions.md`.
  - Python 3.11+, strict typing (`pathlib`, type hints), NumPy-style docstrings.
- **Tests:** Follow `.github/instructions/testing.instructions.md`.
  - Use `pytest` (no `unittest`), place in `tests/`, mirroring source.
  - All tests must pass before completion.

---

## 4. Documentation & CI

- Update documentation and CLI help for user-facing changes.
- Local checks (`pixi run ...`) must match CI.
- Do not reduce code quality or coverage without approval.

---

## 5. Handling Ambiguities

- If instructions are unclear or conflict, ask for clarification.
- If a pixi task is missing/fails, do not invent commands—ask for guidance.
- Stop and consult if stuck in a validation loop.
