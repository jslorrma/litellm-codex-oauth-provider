
# Review Instructions

Use the following guidelines to review Python code for compliance with the Modern Python Style Guide, following PEP 8 and PEP 20. Ensure the code adheres to Python 3.10+ best practices, leverages modern language features effectively, and follows established coding standards for clarity, performance, and maintainability.

## Steps

1. **Assess Code for Modern Python Features**
    - Review code to ensure the use of:
      - Comprehensions (`list`, `dict`, or set comprehensions) for concise and efficient loops.
      - F-strings for string formatting.
      - The walrus operator (`:=`) to simplify expressions and minimize redundant logic.
      - Pattern matching (`match` and `case`) for handling complex branching logic.
      - Context managers (`with`) for safe resource handling.
      - Decorators for reusable functionality.
      - Dataclasses for defining simple data structures.
      - Generator expressions for handling large data sets efficiently.
    - Verify that these features are incorporated only where appropriate and enhance code clarity.

2. **Enforce Type Annotations**
    - Confirm all functions and methods explicitly define type annotations for parameters and return values:
      - Use `list[T]`, `Sequence[T]`, and `dict[K, V]` as necessary.
      - Use `X | None` for optional types, avoiding `Union[T, None]`.
      - Default return type is `-> None` if the function does not return any value.
      - Leverage abstract base classes like `Sequence` or `Mapping` for interface-like behavior when appropriate.
    - Check for the use of `from __future__ import annotations` for postponed type annotations.

3. **Verify Code Style and Organization**
    - Ensure adherence to PEP 8, Google's Python Style Guide, and a 100-character line length.
    - Check for structured import blocks:
      - Group imports into: `future` imports --> standard library imports --> third-party --> local imports.
      - Import file and directory handling using `pathlib`.
      - Keep type-hint imports within a conditional `if TYPE_CHECKING:` block.
    - Call out any magic constants or repetition in logic, recommending reuse or refactoring where necessary.

4. **Review Documentation**
    - Check the use of the **NumPy docstring format** for:
      - Functions, methods, and classes.
      - Summary, Parameters, Returns, Examples, Notes, Raises, and See Also sections.
    - Confirm presence and correctness of module-level docstrings summarizing the file's purpose.
    - Ensure documentation reflects all edge cases and includes relevant examples.
    - Review attribute-level and local helper function documentation to maintain clarity.

5. **Assess Code for Tool Compliance**
    - Verify formatting with `ruff format` and linting with `ruff`.
    - Recommend correction of any findings from these tools, especially around unused imports, styling, or type violations.
    - Validate that code is formatted consistently following the project's tooling configuration.

6. **Ensure Code Functionality**
    - Confirm that inputs, outputs, and expected behaviors are correctly handled.
    - Review error handling and edge case coverage for robustness.
    - Check that tests exist for complex or non-obvious functionality, and examples are provided for clarity.

## Examples

**Example Input (Code to Review):**

```python
def capitalize_words(sentence):
    words = []
    for word in sentence.split():
        words.append(word.capitalize())
    return " ".join(words)
```

**Example Output (Code Review):**

Summary:

- The code is functional but misses opportunities to leverage modern Python idioms and lacks type annotations.

Detailed Feedback:

- **Style and Syntax**: Replace the explicit loop with a comprehension for conciseness.
- **Modern Python Features**: Use f-string for improved clarity when joining words.
- **Type Annotations**: Add annotations for `sentence` parameter and return type.
- **Documentation**: Include a docstring describing the function's behavior and examples.
- **Testing**: Ensure edge cases like empty input and special characters are handled.

Action Items:

- Rewrite the loop as a comprehension.
- Add a docstring and type annotations.
- Handle edge cases and document their behavior.

**Refactored Code:**

```python
def capitalize_words(sentence: str) -> str:
    """Capitalize the first letter of each word in a sentence.

    Parameters
    ----------
    sentence : str
        A sentence to process.

    Returns
    -------
    str
        The processed sentence with each word capitalized.

    Example
    -------
    >>> capitalize_words("hello world")
    'Hello World'
    """
    return " ".join(word.capitalize() for word in sentence.split())
```

---

**Example Input (Adding Context Managers):**

```python
def write_to_file(filename, content):
    file = open(filename, "w")
    file.write(content)
    file.close()
```

**Example Output (Code Review):**

Summary:

- The function works but risks resource leaks and does not use best practices for file handling or type annotations.

Detailed Feedback:

- **Style and Syntax**: Replace manual open/close logic with a context manager.
- **Modern Python Features**: Utilize `pathlib.Path` for file handling.
- **Type Annotations**: Add annotations for `filename` and `content`.
- **Documentation**: Provide an example and describe the function's behavior.

Action Items:

- Use a `with` statement for file handling.
- Update `filename` to `pathlib.Path`.
- Add type annotations and a docstring.

**Refactored Code:**

```python
from pathlib import Path

def write_to_file(filename: Path, content: str) -> None:
    """Write content to a file safely.

    Parameters
    ----------
    filename : Path
        Path to the file to write to.
    content : str
        The content to write into the file.

    Returns
    -------
    None

    Example
    -------
    >>> write_to_file(Path("example.txt"), "Hello, World!")
    """
    with filename.open("w") as file:
        file.write(content)
```

## Notes

- Prioritize modernization without compromising readability or maintainability.
- Encourage concise, Pythonic logic while documenting all enhancements systematically.
- Ensure edge cases and unexpected behaviors are well-explained in the review.
