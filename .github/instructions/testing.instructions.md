---
applyTo: "**/tests/**/*.py, **/test_*.py, **/TEST_*.py"
description: "Modern Python testing guidelines for writing and reviewing tests"
---

# Python Testing Guidelines

Use these guidelines when writing or reviewing tests. Prefer clear, maintainable tests built on `pytest`, fixtures, and modern mocking patterns.

---

## Core Principles

- Use `pytest` as the testing framework.
  - **Never mix** `pytest` with `unittest` features (`unittest.TestCase`, `unittest.mock`, etc.).
  - Use only `pytest` features, `pytest-mock`, or `monkeypatch`.
- Each test module must have a module-level docstring describing its scope and behavior.
- Focus tests on user-visible behavior, contracts, and error handling—not implementation details.
- Keep tests small, focused, and deterministic.
- Avoid network access, real disk I/O, or timing-based flakiness unless required; use mocks, fixtures, or other isolation techniques instead.

---

## Structure and Organization

- Structure tests with the **given–when–then** pattern (in comments, docstrings, or test names) to clarify intent.
- Use descriptive test names (e.g., `test_function_returns_value_on_valid_input`, `test_api_returns_404_for_missing_resource`).
- Group reusable setup into fixtures instead of duplicating setup code.
- Separate fixtures and tests using clear section headers, following this pattern:

  ```
  # =============================================================================
  # FIXTURES
  # =============================================================================

  @pytest.fixture
  def my_fixture():
      ...

  # =============================================================================
  # TESTS
  # =============================================================================

  def test_my_function(my_fixture):
      ...
  ```

- Module order: module docstring → `from __future__ import annotations` (if used) → imports → fixtures → tests.

---

## Fixtures

- Use `@pytest.fixture` for reusable setup or test data.
- Select fixture scope (`function`, `module`, `session`, etc.) based on setup cost and test isolation needs.
- Prefer parametrized fixtures or `@pytest.mark.parametrize` for multiple input cases.
- Keep fixtures focused—each should set up a clear, single purpose.
- Use fixtures for both data and infrastructure setup; use teardown semantics (context managers, `yield` fixtures) for cleanup.

---

## Mocking and Monkey-Patching

- Use `pytest-mock` (`mocker` fixture) or `monkeypatch` to isolate external dependencies/side effects.
  - Use `mocker.patch` for patching callables/attributes where inspection is needed (call counts, arguments).
  - Use `monkeypatch.setattr` or `monkeypatch.setenv` for simple attribute or environment overrides.
- Ensure mocks/patches are scoped to the test or fixture and cleaned up automatically.
- **Do not use** `unittest.mock` or manual patching helpers.

---

## Coverage and Scenarios

- Cover all relevant code paths, including branches (`if`, `match`/`case`, early returns).
- Test edge cases, invalid inputs, and error-handling paths—not just happy paths.
- Use `pytest.raises` to test for expected exceptions and validate error messages/types.
- Parametrize tests for multiple scenarios, especially for data-driven cases.
- For new features, include tests for typical usage and boundary conditions.

---

## Documentation and Readability

- Name fixtures and test functions descriptively to communicate setup or verification intent.
- Use short comments or docstrings in tests to clarify non-obvious behavior, especially for mocks or edge cases.
- Keep test bodies linear and easy to scan; use a **given–when–then** structure with minimal nesting.
- Avoid redundant comments—document intent, constraints, or tricky details only.

---

## Tooling

- Run tests using `pytest`, typically via the project's task runner (e.g., `pixi run test`).
- Use coverage tools (e.g., `pytest-cov`) if configured, and avoid untested critical paths.
- Follow project-specific configuration for markers, test selection, and plugins (in `pyproject.toml`, `pytest.ini`, etc.).

---

## Example

**Original (to refactor)**

```python
import unittest
import requests

class TestAPI(unittest.TestCase):
    def test_fetch_data(self):
        url = "https://example.com/api/data"
        response = requests.get(url)
        assert response.status_code == 200
        assert response.json() == {"key": "value"}
```

**Refactored `pytest` style**

```python
"""Tests for API data fetching behavior."""
from __future__ import annotations
from collections.abc import Callable
import pytest
from pytest_mock import MockerFixture
import requests

# =============================================================================
# FIXTURES
# =============================================================================
@pytest.fixture
def mock_api_response(mocker: MockerFixture) -> Callable[..., requests.Response]:
    """Return a mock for requests.get that yields a successful API response."""
    class MockResponse:
        status_code = 200

        @staticmethod
        def json() -> dict[str, str]:
            return {"key": "value"}

    def _mock_get(*_: object, **__: object) -> MockResponse:
        return MockResponse()

    mocker.patch("requests.get", _mock_get)
    return _mock_get

# =============================================================================
# TESTS
# =============================================================================
def test_fetch_data_returns_expected_payload(mock_api_response: Callable[..., requests.Response]) -> None:
    """Given a successful API call, when data is fetched, then the JSON payload matches expectations."""
    url = "https://example.com/api/data"
    response = requests.get(url)
    assert response.status_code == 200
    assert response.json() == {"key": "value"}
```

---

## Compliance Checklist

- `pytest` is used exclusively; no `unittest` features.
- Fixtures provide reusable and automatically cleaned-up setup.
- Mocks use `pytest-mock` or `monkeypatch`, not `unittest.mock`.
- Tests are named and structured for clear given–when–then readability.
- Behavior and edge cases are covered with parametrization and additional tests as needed.
