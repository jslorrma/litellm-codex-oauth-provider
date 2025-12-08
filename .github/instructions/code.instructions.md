---
applyTo: "**/*.py,**/*.pyi,**/pyx"
description: "Modern Python coding standards"
---

# Python Coding Guidelines

Use the provided Modern Python Style Guide to write or review Python code with an emphasis on efficient and modern Python language features. The code should make use of comprehensions, f-strings, walrus operators, pattern matching, context managers, generator expressions, decorators, and dataclasses where applicable. Ensure the code adheres to outlined standards, including type annotations, imports, path handling, documentation, and code organization.

## Steps

1. **Understand the Guide**:
    - Familiarize yourself with the core principles of Pythonic, modern design, following PEP 8 and PEP 20.
    - Incorporate features such as comprehensions, f-strings, walrus operators, pattern matching, decorators, and dataclasses where appropriate.

2. **Incorporate Modern Python Features**:
    - Use list/dict comprehensions for concise and efficient loops.
    - Use f-strings for string formatting.
    - Use the walrus operator (`:=`) for assignment during expressions to simplify code.
    - Leverage pattern matching (`match` statements) for complex branching logic.
    - Utilize context managers (`with` statements) for resource handling.
    - Use generator expressions to handle large data sets efficiently.
    - Use decorators to add reusable functionality to functions or methods.
    - Replace verbose class definitions with `dataclasses` for simple data structures or tuples returned from functions.

3. **Enhance Code Style**:
    - Assume Python 3.10 or later and leverage its features fully.
    - Follow pep8 and Google's Python Style Guide for consistency.

4. **Add Type Annotations**:
    - Use modern syntax for type hints (`X | None`, `list[T]`).
    - Explicitly define types for all function parameters and return values.
    - Use abstract base classes like `Sequence` where read-only access suffices.
    - Use `list[T]` for mutable sequences of type T
    - Use `-> None` explicitly when a function doesn't return anything
    - For multiple return types, use the union operator

5. **Organize Imports and Maintain Path Handling**:
    - Properly structure imports into three groups: future, standard library, and third-party/local imports.
    - Put `from __future__ import annotations` at the top of each file to enable postponed evaluation of type annotations.
    - Replace `os.path` with `pathlib.Path` for file and directory operations.
    - Always import `pathlib` module for path handling, instead of just the `Path` class.
    - Import collection types from `collections.abc`
    - Move any imports just for type hints into a separate `if TYPE_CHECKING:` block.

6. **Write Clear Documentation**:
    - Use NumPy docstring format, including sections like Summary, Parameters, Returns, Examples, Notes, Raises, and See Also.
    - Always include a module-level docstring describing the purpose of the module and add examples and additional notes where necessary.
    - Document type aliases, constants, and variables with clear, concise descriptions.
    - Add docstrings for each function, method, or class attribute to explain its purpose and usage, including examples where relevant.
    - Class docstrings should describe the purpose of the class and its attributes.
    - Local helper functions or methods should have only a one-line summary and a brief description if necessary.
    - Remember that good documentation should:
      - Be clear and concise
      - Include all necessary information
      - Be kept up-to-date with code changes
      - Include examples for non-obvious usage
      - Document exceptions and edge cases
      - Maintain consistency across the project

7. **Utilize Tooling**:
    - Format code with `ruff format`, apply a 100-character line length limit, and use `ruff` for linting.

## Examples

**Example Input (Code to Refactor):**

```python
def get_squares_with_filter(numbers):
    result = []
    for n in numbers:
        if n > 0:
            result.append(n ** 2)
    return result
```

**Example Output (Refactored Code):**

```python
from typing import Sequence

def get_squares_with_filter(numbers: Sequence[int]) -> list[int]:
    """Filter positive numbers and compute their squares.

    Parameters
    ----------
    numbers : Sequence[int]
        A sequence of integers to process.

    Returns
    -------
    list[int]
        A list containing the squares of positive integers from the input sequence.

    Example
    -------
    >>> get_squares_with_filter([-1, 2, 3, -4])
    [4, 9]
    """
    return [n ** 2 for n in numbers if n > 0]
```

**Compliance Checklist**:

- **Modern Features**: ✅ Used comprehensions, f-strings, pattern matching, and dataclasses.
- **Type Hints**: ✅ Explicit type hints for functions and return types.
- **Code Organization**: ✅ Imports grouped and code formatted consistently.
- **Documentation**: ✅ Clear, reusable NumPy docstrings. Included examples.

## Notes

- Encourage concise and expressive use of decorators, dataclasses, and generator expressions to simplify logic.
- Ensure edge cases are documented and handled appropriately.
- Refactor examples demonstrate modern Python idioms with clear, reusable code.
