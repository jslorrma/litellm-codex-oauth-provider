---
applyTo: "**/tests/**/*.py"
description: "Modern Python Testing Best Practices to be used when writing or reviewing tests"
---

# Python Testing Guidelines

Use the provided Modern Python Testing Best Practices to write new tests or review/refactor existing ones. Ensure the tests adhere to the outlined standards, incorporating fixtures, mocking, monkey-patching, behavior-driven testing (`given-when-then` structure), and utilizing `pytest` as the testing framework. Emphasize clear, concise, maintainable testing code.

## Steps

1. **Understand the Standards**:
   - Familiarize yourself with modern testing practices for Python using `pytest`.
   - Avoid `unittest` or older frameworks in favor of `pytest` for simplicity and flexibility.
   - Use fixtures for reusable setup and teardown functionality.
   - Leverage mocking and monkey-patching for isolating functionality and simulating dependencies.
   - Follow the `given-when-then` behavior-driven structure to improve test readability and organization.

2. **Fixtures - When and How to Use**:

   **Use fixtures pragmatically based on clear criteria:**

   **✅ USE FIXTURES when:**
   - Data/setup is **reused in 3+ tests** (eliminates duplication, single source of truth)
   - Setup is **complex (5+ lines)** (separates setup from behavior testing)
   - Resources **need teardown** (ensures proper cleanup - files, connections, etc.)
   - **Parameterization adds value** (runs same test with different inputs)
   - Operation is **expensive** (I/O, computation - use module/session scope)

   **⚠️ KEEP INLINE when:**
   - Data is **simple (1-3 lines)** (easier to understand at a glance)
   - Data is **test-specific/unique** (no reuse benefit)
   - **Readability priority** (context visible without scrolling)
   - **Debugging matters** (immediate data inspection)

   **Implementation guidelines:**
   - Use `@pytest.fixture` to create reusable components for setting up initial conditions
   - Scope fixtures appropriately (`function`, `module`, or `session`) based on requirements
   - Prefer parameterized fixtures (`@pytest.fixture(params=[...])`) for varying test data
   - Ensure fixtures are concise and focused on their purpose
   - Name fixtures descriptively to document their purpose (e.g., `minimal_valid_config`, `mock_api_response`)

   **Example - Good fixture usage (reused data):**
   ```python
   @pytest.fixture
   def minimal_valid_config() -> dict:
       """Minimal valid configuration for testing."""
       return {
           "runtime": {"profile": "dev"},
           "pipeline": {"enabled": True, "concurrency": 1},
       }

   def test_load_minimal(config_loader, minimal_valid_config):
       cfg = config_loader.load(minimal_valid_config)
       assert cfg.pipeline.enabled is True

   def test_load_with_override(config_loader, minimal_valid_config):
       minimal_valid_config["pipeline"]["concurrency"] = 4  # Customize
       cfg = config_loader.load(minimal_valid_config)
       assert cfg.pipeline.concurrency == 4
   ```

   **Example - Good inline usage (test-specific):**
   ```python
   def test_step_stores_dependencies():
       """Test @step decorator captures dependencies."""
       # Given - test-specific function (used only once)
       @step(depends_on=("load", "validate"))
       def transform(x: int) -> int:
           return x

       # Then
       meta = get_step_meta(transform)
       assert meta.depends_on == ("load", "validate")
   ```

3. **Test Data Management**:

   **Decision tree for test data:**

   ```
   Is data reused in 3+ tests?
   └─ YES → Use fixture
   └─ NO  → Is it complex (5+ lines)?
            └─ YES → Consider fixture for clarity
            └─ NO  → Keep inline (1-3 lines)
   ```

   **Fixtures for test data (when reused):**
   ```python
   @pytest.fixture
   def base_config_dict() -> dict:
       """Reusable baseline configuration."""
       return {"key": "value", "nested": {"data": 123}}

   def test_one(base_config_dict):
       base_config_dict["key"] = "modified"  # Customize as needed
       # ... test logic
   ```

   **Inline for unique data (simple, one-time use):**
   ```python
   def test_merge_dicts():
       """Test dict merging with simple inline data."""
       # Given - simple, unique data visible at a glance
       base = {"a": 1, "b": 2}
       overlay = {"b": 3, "c": 4}

       # When
       result = merge(base, overlay)

       # Then
       assert result == {"a": 1, "b": 3, "c": 4}
   ```

4. **Mocking and Monkey-Patching**:

   **Environment variable patching:**

   **Use fixtures for environment setup when reused:**
   ```python
   @pytest.fixture
   def pipeline_env_vars(monkeypatch):
       """Set up standard pipeline environment variables."""
       env_vars = {
           "BITC__PIPELINE__CONCURRENCY": "8",
           "BITC__USE_CASE__ENABLED": "true",
       }
       for key, value in env_vars.items():
           monkeypatch.setenv(key, value)
       return env_vars

   def test_one(pipeline_env_vars):
       # Environment already set up
       ...

   def test_two(pipeline_env_vars):
       # Reused across tests
       ...
   ```

   **Keep inline for test-specific env setup:**
   ```python
   def test_env_overlay(monkeypatch):
       """Test with specific env vars unique to this test."""
       # Given - explicit, clear what's being set
       monkeypatch.setenv("BITC__SPECIFIC_VAR", "test_value")
       monkeypatch.setenv("BITC__ANOTHER_VAR", "42")
       # ... test logic
   ```

   **General mocking guidelines:**
   - Use `pytest-mock` for mocking dependencies, external APIs, or resource-intensive operations
   - Use `monkeypatch` from `pytest` for dynamically replacing module or object attributes in controlled test scenarios
   - Choose either `pytest-mock` or `monkeypatch` based on the complexity and requirements of the test
   - Ensure mocks and patches are cleaned up after use
   - Write mocks for external calls or side effects while testing only the local logic

5. **Behavior-Driven Testing**:
   - Structure tests using the `given-when-then` format:
     - **Given**: Set up the prerequisites and context for the test.
     - **When**: Perform the action or behavior under test.
     - **Then**: Assert the expected outcomes or results.
   - Name test functions descriptively, indicating the behavior being tested, e.g., `test_function_returns_value_on_valid_input`.

6. **Test Coverage**:
   - Ensure tests cover a wide range of paths, edge cases, and failure scenarios.
   - Use parameterized tests for validating multiple inputs and cases with minimal boilerplate.
   - Focus on testing user-facing behavior rather than implementation details.

7. **Documentation and Code Clarity**:
   - Use descriptive names for test functions, fixtures, and parameters to improve readability.
   - Add in-line comments where necessary, especially for complex mocks or patches.
   - Ensure tests are easy to understand, with redundant or unnecessary setup avoided.
   - Separate definitions, fixtures, and tests with bold, clear, concise comments for better organization, like:

      ```python
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

8. **Tooling**:
   - Use `pytest` plugins (`pytest-mock`, `pytest-cov`) to enhance functionality.
   - Track code coverage with `pytest-cov` and aim for high coverage, avoiding untested critical paths.

## Quick Reference: Fixture vs Inline Decision

**Before writing test data, ask:**

1. **Is it reused in 3+ tests?** → YES = Fixture | NO = Continue
2. **Is it complex (5+ lines)?** → YES = Consider fixture | NO = Continue
3. **Does it need cleanup?** → YES = Fixture with yield | NO = Continue
4. **Is it expensive (I/O)?** → YES = Module/session fixture | NO = Continue
5. **Is it test-specific?** → YES = Keep inline
6. **Is it simple (1-3 lines)?** → YES = Keep inline

**Example patterns:**

| Pattern | Use |
|---------|-----|
| Config dict used in 6 tests | Fixture |
| Simple `base = {"a": 1}` | Inline |
| Environment vars in 1 test | Inline |
| Environment vars in 5 tests | Fixture |
| Test-specific decorated function | Inline |
| Expensive DB connection | Session fixture |


## Examples

**Example Input (Existing Test to Refactor):**

```python
import unittest
import os
import requests

class TestAPI(unittest.TestCase):
    def test_fetch_data(self):
        url = "https://example.com/api/data"
        response = requests.get(url)
        assert response.status_code == 200
        assert response.json() == {"key": "value"}
```

**Example Output (Enhanced `pytest` Test):**

```python
"""Module for testing API interactions using pytest."""

from __future__ import annotations

import pytest
from requests.exceptions import HTTPError
from pytest_mock import MockerFixture

import requests

# =============================================================================
# FIXTURES
# =============================================================================
@pytest.fixture
def mock_api_response(monkeypatch: pytest.MonkeyPatch):
    """Fixture to mock API response for the 'requests.get' method."""
    class MockResponse:
        """Mock response class for API testing."""
        # mock status_code attribute always returns 200
        status_code = 200

        # mock json() method always returns a specific testing dictionary
        @staticmethod
        def json():
            return {"key": "value"}

    def mock_get(*args, **kwargs):
        """Mock 'requests.get' method to return the MockResponse."""
        return MockResponse()

    monkeypatch.setattr(requests, "get", mock_get)

@pytest.fixture
def mock_api_error_response(mocker: MockerFixture):
    """Fixture to mock API response that raises an HTTPError."""
    def mock_get(*args, **kwargs):
        raise HTTPError("API Error")

    mocker.patch("requests.get", mock_get)

# =============================================================================
# TESTS
# =============================================================================
def test_fetch_data_with_valid_response(mock_api_response: pytest.MonkeyPatch) -> None:
    """
    Given: A mock API response with status 200 and JSON content.
    When: The fetch_data function calls the API.
    Then: The response JSON matches the expected value.
    """
    url = "https://example.com/api/data"
    response = requests.get(url)
    assert response.status_code == 200
    assert response.json() == {"key": "value"}

def test_fetch_data_with_invalid_response(mock_api_error_response: MockerFixture) -> None:
    """
    Given: An API that raises an HTTPError for a request.
    When: The fetch_data function attempts to call the API.
    Then: An HTTPError is raised, and the error is correctly handled.
    """
    url = "https://example.com/api/data"
    with pytest.raises(HTTPError):
        requests.get(url)

```

**Compliance Checklist**:

- **Use of pytest**: ✅ Replaced unittest with pytest.
- **Fixtures**: ✅ Utilized a fixture to mock API responses (mock_api_response).
- **Mocking and Monkey-Patching**: ✅ Used pytest.monkeypatch in first exmple and pytest-mock in second for overriding requests.get dynamically.
- **Given-When-Then**: ✅ Followed the given-when-then structure for readability and organization.
- **Documentation**: ✅ Added docstrings to each test for easier comprehension.
- **Organization**: ✅ Separated fixtures and tests using bold comments for clarity and structure.
- **Test Coverage**: ✅ Tested both valid and invalid API responses.

**Notes**:

- Ensure that all exceptions are explicitly tested.
- Apply mocks or monkey-patching for more complex examples, such as HTTP requests or external APIs.
