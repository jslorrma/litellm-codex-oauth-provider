"""Simplified authentication module for the LiteLLM Codex OAuth Provider.

This module provides streamlined OAuth token handling from Codex CLI's auth.json file.
It focuses on core functionality while maintaining essential security and reliability.

Key Features:
- Simple token extraction from auth.json
- JWT account ID decoding
- Basic validation and error handling
- Clean, maintainable code structure

The simplified version removes complex caching layers, multiple format handling,
and extensive validation while preserving core authentication functionality.
"""

from __future__ import annotations

import base64
import json
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from . import constants
from .exceptions import (
    CodexAuthFileNotFoundError,
    CodexAuthRefreshError,
    CodexAuthTokenError,
    CodexAuthTokenExpiredError,
)

if TYPE_CHECKING:
    from pathlib import Path


@dataclass(frozen=True)
class AuthContext:
    """Simplified authentication context from auth.json.

    Attributes
    ----------
    access_token : str
        OAuth bearer token for API authentication
    account_id : str
        ChatGPT account ID extracted from JWT token claims
    """

    access_token: str
    account_id: str


def _get_auth_path() -> Path:
    """Get the path to Codex auth.json file.

    Returns
    -------
    Path
        Path to the Codex auth.json file.

    Raises
    ------
    CodexAuthFileNotFoundError
        If the auth file is not found.
    """
    auth_file = constants.DEFAULT_CODEX_AUTH_FILE
    if not auth_file.exists():
        raise CodexAuthFileNotFoundError(
            f"Codex auth file not found at {auth_file}. Please run 'codex login' first."
        )
    return auth_file


def _load_auth_data() -> dict[str, Any]:
    """Load and parse auth.json from Codex CLI.

    Returns
    -------
    dict[str, Any]
        Parsed auth data from the JSON file.

    Raises
    ------
    CodexAuthTokenError
        If there's an error reading or parsing the auth file.
    """
    auth_path = _get_auth_path()

    try:
        with auth_path.open() as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        raise CodexAuthTokenError(f"Failed to parse Codex auth data: {e}") from e
    except Exception as e:
        raise CodexAuthTokenError(f"Failed to read Codex auth data: {e}") from e


def _extract_bearer_token() -> str:
    """Extract the OAuth bearer token from Codex auth data.

    Simplified version that handles the most common auth.json structure.

    Returns
    -------
    str
        The access token.

    Raises
    ------
    CodexAuthTokenError
        If no access token is found.
    CodexAuthTokenExpiredError
        If the token has expired.
    """
    auth_data = _load_auth_data()

    # Handle nested structure: {"chatgpt": {"access_token": "...", ...}}
    if "chatgpt" in auth_data:
        token_data = auth_data["chatgpt"]
    # Handle nested structure: {"tokens": {"access_token": "...", ...}}
    elif "tokens" in auth_data:
        token_data = auth_data["tokens"]
    # Handle flat structure: {"access_token": "...", ...}
    elif "access_token" in auth_data:
        token_data = auth_data

    access_token = token_data.get("access_token")
    if not access_token:
        raise CodexAuthTokenError("No access_token found in Codex auth data")

    # Check expiry if available
    expires_at = token_data.get("expires_at")
    if expires_at and expires_at < time.time():
        raise CodexAuthTokenExpiredError(
            "Codex OAuth token has expired. Please run 'codex login' to refresh your authentication and get a new token."
        )

    return access_token


def _decode_account_id(access_token: str) -> str:
    """Decode the ChatGPT account ID from the JWT access token.

    Parameters
    ----------
    access_token : str
        JWT access token from auth.json

    Returns
    -------
    str
        ChatGPT account ID

    Raises
    ------
    CodexAuthTokenError
        If account ID cannot be decoded
    """
    try:
        # Decode JWT payload (base64 URL-safe)
        _, payload_b64, _ = access_token.split(".")
        padding = "=" * (-len(payload_b64) % 4)
        payload = json.loads(base64.urlsafe_b64decode(payload_b64 + padding))

        # Extract account ID from claims
        account_claim = payload.get(constants.JWT_ACCOUNT_CLAIM, {})
        account_id = account_claim.get("chatgpt_account_id")

        if not account_id:
            raise CodexAuthTokenError("No chatgpt_account_id found in token claims")

        return str(account_id)

    except Exception as exc:
        raise CodexAuthTokenError("Failed to decode ChatGPT account ID from token") from exc


def get_auth_context() -> AuthContext:
    """Get authentication context from Codex auth.json.

    This function provides a simplified authentication flow:
    1. Load and parse auth.json
    2. Extract bearer token
    3. Decode account ID from JWT
    4. Return as AuthContext object

    Returns
    -------
    AuthContext
        Object containing bearer token and account ID.

    Raises
    ------
    CodexAuthFileNotFoundError
        If the Codex CLI auth.json file is not found.
        Please run 'codex login' to authenticate first.
    CodexAuthTokenError
        If there's an issue with token format or decoding.
    CodexAuthTokenExpiredError
        If the access token has expired. Please run 'codex login' to refresh.

    Examples
    --------
    >>> from litellm_codex_oauth_provider.auth import get_auth_context
    >>> context = get_auth_context()
    >>> print(f"Token: {context.access_token[:20]}...")
    >>> print(f"Account ID: {context.account_id}")
    """
    # Extract bearer token
    token = _extract_bearer_token()

    # Decode account ID from JWT
    account_id = _decode_account_id(token)

    return AuthContext(access_token=token, account_id=account_id)


# Legacy function for backward compatibility
def _decode_account_id_old(access_token: str) -> str:
    """Legacy function name for backward compatibility."""
    return _decode_account_id(access_token)


def _refresh_token() -> str:
    """Refresh the access token using the refresh token.

    This function loads the auth data and attempts to refresh the access token.
    Raises CodexAuthRefreshError if no refresh token is available or refresh fails.

    Returns
    -------
    str
        The new access token

    Raises
    ------
    CodexAuthRefreshError
        If no refresh token is available or refresh fails
    """
    auth_data = _load_auth_data()
    chatgpt_data = auth_data.get("chatgpt", {})
    refresh_token = chatgpt_data.get("refresh_token")

    if not refresh_token:
        raise CodexAuthRefreshError(
            "No refresh token available in auth data. "
            "Please ensure your auth.json file includes a 'refresh_token' field."
        )

    # TODO: Implement actual token refresh logic
    # For now, just raise an error since the refresh logic isn't implemented
    raise CodexAuthRefreshError(
        "Token refresh functionality is not yet implemented. "
        "Please manually update your access token."
    )


def get_bearer_token() -> str:
    """Get bearer token from auth context.

    This is a convenience function that extracts just the bearer token
    from the authentication context.

    Returns
    -------
    str
        The bearer token for API authentication

    Raises
    ------
    Exception
        Any exception raised by get_auth_context()
    """
    context = get_auth_context()
    return context.access_token
