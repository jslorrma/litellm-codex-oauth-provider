---
applyTo: "**/*.py,**/*.pyi,**/*.pyx"
description: "Modern Python coding standards and design philosophy for writing and reviewing Python code"
---

# Python Coding Guidelines & Design Philosophy

Use this guide when writing or reviewing Python code in this repository. All code must be clean, well-structured, maintainable, and tested. Favor modern, typed, and idiomatic Python that strictly follows both project conventions and tooling.

---

## Guiding Philosophy

### Clean Code is Non-Negotiable

Clean code is a fundamental requirement for every piece of software we write.

- **Simple & Readable:** Code should be immediately understandable and self-explanatory. Avoid unnecessary complexity.
- **Well-Structured & Maintainable:** Follow "convention over configuration" for consistent organization and clear separation of concerns.
- **Consistent:** Adhere to shared standards and conventions for uniformity across the codebase.
- **Testable:** Design code for automated verification; every unit should be easy to test.
- **Efficient:** Optimize for performance without sacrificing clarity or maintainability.

### Core Design Patterns & Principles

- **DRY (Don't Repeat Yourself):** Avoid duplication—centralize logic to reduce maintenance and ensure consistency.
- **KISS (Keep It Simple, Stupid):** Prefer simple, clear solutions over complex or clever constructs.
- **YAGNI (You Ain't Gonna Need It):** Build only what is required now; avoid speculative features.
- **SoC (Separation of Concerns):** Isolate unrelated responsibilities into distinct modules/functions.
- **SRP (Single Responsibility Principle):** Functions/classes should do one thing well and have a single reason to change.
- **Open/Closed Principle:** Code should be open for extension but closed for modification. Prefer extensible designs.
- **Composition over Inheritance:** Use composition, protocols (`typing.Protocol`), and duck typing for code reuse and flexibility rather than deep inheritance hierarchies.

---

## Core Principles

- Assume Python 3.11+ unless specified otherwise.
- Follow the Zen of Python (PEP 20) and PEP 8 style, unless overridden by project-specific guidelines.
- Write clear, maintainable, and well-documented code.
- Prefer solutions that are simple, readable, and maintainable.
- Use modern Python features only when they genuinely improve clarity or structure.

---

## Type Annotations

- Use modern type syntax: `X | None`, `list[T]`, `dict[str, T]`, etc.
- Annotate all public functions, methods, and class attributes.
- Use `-> None` for functions that do not return a value.
- Use abstract base classes (`Sequence`, `Mapping`, `Iterable`) for generic/read-only access.
- Use concrete types (`list[T]`, `set[T]`, `dict[K, V]`) for mutable collections.
- Avoid quoted type annotations; enable postponed evaluation with `from __future__ import annotations`.

---

## Imports & Path Handling

- Group imports in this order, separated by blank lines:
  1. Future imports
  2. Standard library imports
  3. Third-party and local/project imports
- Always include a module-level docstring at the top of each file.
- Place `from __future__ import annotations` immediately after the module docstring.
- Prefer `pathlib` over `os.path` for filesystem paths; use `import pathlib` rather than `from pathlib import Path`.
- Import collection types (`Iterable`, `Mapping`, `Sequence`) from `collections.abc`.
- Move imports used only for typing into an `if TYPE_CHECKING:` block.

---

## Documentation

- Use NumPy-style docstrings for all modules, classes, and functions.
- Always provide a module-level docstring describing the file's purpose, context, and conventions.
- Public API modules must include:
  - Clear summary of purpose and behavior
  - Reproducible examples (with imports)
  - Notes on usage or edge cases
- Public API classes/functions/methods must include:
  - User-focused docstrings explaining usage and only necessary implementation details
  - Purpose and behavior summary
  - Complete Parameters section (if arguments are non-trivial)
  - Returns section (only if returning a value)
  - Raises section (only if exceptions are documented)
  - At least one reproducible example in an Examples section
  - Notes for additional context
- Internal/helper functions:
  - Maintainers-focused docstrings explaining implementation details
  - Purpose and behavior summary
  - Provide concise docstrings focused on implementation details
  - Include Parameters and Returns sections as appropriate
  - Omit extensive examples unless function is complex
  - Use Notes for clarifications or caveats
  - Small internal helpers (<5 lines) may use single-line docstrings
- Use cross-references (`See Also`) to link related functions/classes.
- Keep documentation accurate and updated with code changes.
- Over-documentation, that is, excessive or does not add value, should be avoided.

---

## Modern Python Features

Use modern features judiciously:

- List/dict comprehensions for building collections.
- Generator expressions for streaming or large data sets.
- F-strings for string formatting.
- Walrus operator (`:=`) for readable control flow—avoid complex use.
- Structural pattern matching (`match`/`case`) for complex branching.
- Context managers (`with`) for resource management.
- Decorators for cross-cutting concerns (e.g., caching, validation).
- `dataclasses`, `NamedTuple`, and `TypedDict` for typed containers.
- Prefer typed containers and protocols over untyped dicts/tuples.
**Do not use modern features just for novelty. Clarity and maintainability always take priority over using the latest features. Avoid overengineering or unnecessary complexity.**

---

## Tooling

- Format code with `ruff format`. Max line length: 100 characters (or project-specific).
- Use `ruff` for linting and fix issues.
- Follow all project-specific configuration for tools (e.g., `ruff`, `mypy`).

---

## Example

**Original code**

```python
def get_squares_with_filter(numbers):
    result = []
    for n in numbers:
        if n > 0:
            result.append(n ** 2)
    return result
```

**Refactored code**

```python
"""Module for numerical transformations and filtering.

Provides functions for transforming sequences of numbers,
including filtering and mapping operations.

Examples
--------
>>> get_squares_with_filter([-1, 2, 3, -4])
[4, 9]

Notes
-----
Zero values are ignored because they are not strictly positive.
"""

from __future__ import annotations
from collections.abc import Sequence

def get_squares_with_filter(numbers: Sequence[int]) -> list[int]:
    """Compute squares of positive integers.

    Parameters
    ----------
    numbers : Sequence[int]
        A sequence of integers to process.

    Returns
    -------
    list[int]
        The squares of positive integers from the input sequence.

    Examples
    --------
    >>> get_squares_with_filter([-1, 2, 3, -4])
    [4, 9]
    """
    return [n**2 for n in numbers if n > 0]
```

---

## Compliance Checklist

- Modern features are used only where they improve clarity and structure.
- Explicit, modern, and unquoted type annotations throughout.
- Imports are grouped and ordered properly; paths use `pathlib`.
- Public APIs have NumPy-style docstrings with examples and notes.
- Internal helpers use concise documentation.
- Code is formatted and linted with configured tooling.
- Code structure, style, and design patterns align with DRY, KISS, YAGNI, SoC, SRP, open/closed, and composition principles.
