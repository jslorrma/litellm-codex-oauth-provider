"""Given Codex auth fixtures and LiteLLM hooks, when tests request fixtures, then consistent

test data and temporary auth files are provisioned for deterministic scenarios.

This conftest module centralizes reusable fixtures for the suite. It builds unsigned JWTs
with expected ChatGPT account claims, writes temporary auth.json files, and patches provider
constants so every test runs against isolated, in-memory credentials. By keeping the auth
surface stable and reproducible, the tests can focus on provider behavior rather than local
environment state.
"""

from __future__ import annotations

import base64
import json
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest

if TYPE_CHECKING:
    from collections.abc import Generator

    from pytest_mock import MockerFixture


# =============================================================================
# FIXTURES
# =============================================================================
def _build_fake_jwt(account_id: str = "mock-account") -> str:
    """Create a minimal unsigned JWT with the expected ChatGPT account claim.

    Generates deterministic header/payload segments so token shape matches what the
    provider expects without needing valid signatures.
    """
    header = {"alg": "none", "typ": "JWT"}
    payload = {"https://api.openai.com/auth": {"chatgpt_account_id": account_id}}

    def _encode(part: dict[str, Any]) -> str:
        raw = json.dumps(part, separators=(",", ":")).encode()
        return base64.urlsafe_b64encode(raw).decode().rstrip("=")

    return f"{_encode(header)}.{_encode(payload)}.signature"


@pytest.fixture
def mock_auth_data() -> dict[str, Any]:
    """Return mock auth data including access, refresh, and expiry fields.

    Provides a realistic structure for auth.json consumers while remaining fully in-memory.
    """
    token = _build_fake_jwt()
    return {
        "chatgpt": {
            "access_token": token,
            "refresh_token": _build_fake_jwt("refresh-account"),
            "expires_at": 9999999999,
        }
    }


@pytest.fixture
def mock_auth_file(
    mock_auth_data: dict[str, Any], mocker: MockerFixture
) -> Generator[Path, None, None]:
    """Create a temporary auth file for testing and patch provider constants.

    Writes the mock auth data to disk, overrides DEFAULT_CODEX_AUTH_FILE to point at the
    temporary location, and yields the path for downstream tests.
    """
    with tempfile.TemporaryDirectory() as temp_dir:
        auth_dir = Path(temp_dir) / ".codex"
        auth_dir.mkdir()
        auth_file = auth_dir / "auth.json"

        with auth_file.open("w") as f:
            json.dump(mock_auth_data, f)

        mocker.patch("litellm_codex_oauth_provider.constants.DEFAULT_CODEX_AUTH_FILE", auth_file)
        yield auth_file
