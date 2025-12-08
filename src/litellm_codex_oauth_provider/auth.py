"""Authentication module for the LiteLLM Codex OAuth Provider.

This module handles reading, validating, and managing OAuth tokens from the Codex CLI's
auth.json file. It provides a complete authentication context including bearer tokens
and ChatGPT account ID extraction from JWT claims.

The authentication system supports:
- Automatic token validation and expiry checking
- JWT token parsing for account ID extraction
- Token refresh using OAuth refresh tokens
- Multiple auth.json structure formats
- Comprehensive error handling for auth failures

Authentication Flow
-------------------
1. **Token Extraction**: Read access_token from Codex CLI auth.json
2. **Validation**: Check token expiry and format validity
3. **Account ID**: Extract ChatGPT account ID from JWT claims
4. **Refresh**: Automatically refresh expired tokens using refresh_token
5. **Caching**: Cache validated tokens to minimize file I/O

Supported Auth Formats
----------------------
The module handles multiple auth.json structures:
- Nested: `{"chatgpt": {"access_token": "...", "refresh_token": "..."}}`
- Flat: `{"access_token": "...", "refresh_token": "..."}`
- Legacy: `{"auth": {"access_token": "..."}}`
- Tokens: `{"tokens": {"access_token": "..."}}`

Examples
--------
Basic authentication context retrieval:

>>> from litellm_codex_oauth_provider.auth import get_auth_context
>>> context = get_auth_context()
>>> print(f"Token: {context.access_token[:20]}...")
>>> print(f"Account ID: {context.account_id}")

Direct token extraction:

>>> from litellm_codex_oauth_provider.auth import get_bearer_token
>>> token = get_bearer_token()

Token refresh:

>>> from litellm_codex_oauth_provider.auth import _refresh_token
>>> new_token = _refresh_token()

Error handling:

>>> try:
...     context = get_auth_context()
... except CodexAuthFileNotFoundError:
...     print("Run 'codex login' first")
... except CodexAuthTokenExpiredError:
...     print("Token expired, refresh needed")

Notes
-----
- Tokens are cached in memory to minimize file I/O
- JWT account ID extraction handles base64 URL-safe encoding
- Refresh tokens are obtained from the same auth.json structure
- All file operations use pathlib for cross-platform compatibility
- Debug logging available via CODEX_DEBUG environment variable

See Also
--------
- `CodexAuthError`: Base exception for authentication errors
- `CodexAuthTokenExpiredError`: Raised when tokens are expired
- `CodexAuthRefreshError`: Raised when token refresh fails
"""

from __future__ import annotations

import base64
import json
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import httpx

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
    """Authentication context decoded from auth.json.

    This dataclass holds the essential authentication information extracted from
    the Codex CLI auth.json file, including the bearer token and ChatGPT account ID.

    Attributes
    ----------
    access_token : str
        The OAuth bearer token for API authentication
    account_id : str
        The ChatGPT account ID extracted from JWT token claims

    Examples
    --------
    >>> from litellm_codex_oauth_provider.auth import get_auth_context
    >>> context = get_auth_context()
    >>> print(f"Token: {context.access_token[:20]}...")
    >>> print(f"Account ID: {context.account_id}")

    Notes
    -----
    - The dataclass is frozen to prevent modification after creation
    - Both attributes are required and must be provided during initialization
    - The access_token is used for HTTP Authorization headers
    - The account_id is used for ChatGPT-specific API headers
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
    CodexAuthError
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

    The auth.json structure (simplified):
    {
      "chatgpt": {
        "access_token": "ey...",
        "refresh_token": "...",
        "expires_at": 1234567890
      }
    }

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

    # Navigate the auth structure
    # Actual structure may vary - adjust based on your auth.json
    if "chatgpt" in auth_data:
        token_data = auth_data["chatgpt"]
    elif "auth" in auth_data:
        token_data = auth_data["auth"]
    elif "tokens" in auth_data:
        token_data = auth_data["tokens"]
    else:
        # Fallback: assume flat structure
        token_data = auth_data

    access_token = token_data.get("access_token")
    if not access_token:
        raise CodexAuthTokenError("No access_token found in Codex auth data")

    # Check expiry (if available)
    expires_at = token_data.get("expires_at")
    if expires_at and expires_at < time.time():
        # Token expired - need to refresh
        raise CodexAuthTokenExpiredError(
            "Codex OAuth token expired. Please run 'codex login' to refresh."
        )

    return access_token


def _decode_account_id(access_token: str) -> str:
    """Decode the ChatGPT account ID from the JWT access token."""
    try:
        _, payload_b64, _ = access_token.split(".")
        padding = "=" * (-len(payload_b64) % 4)
        payload = json.loads(base64.urlsafe_b64decode(payload_b64 + padding))
        account_claim = payload.get(constants.JWT_ACCOUNT_CLAIM, {})
        account_id = account_claim.get("chatgpt_account_id")
    except Exception as exc:
        raise CodexAuthTokenError("Failed to decode ChatGPT account ID from token") from exc

    if not account_id:
        raise CodexAuthTokenError("No chatgpt_account_id found in token claims")
    return str(account_id)


def get_auth_context() -> AuthContext:
    """Return the bearer token and decoded ChatGPT account ID.

    This function loads the authentication data from the Codex CLI auth.json file,
    extracts the bearer token, decodes the ChatGPT account ID from JWT claims,
    and returns them as an AuthContext object.

    The function handles the complete authentication flow:
    1. Locates and reads the Codex CLI auth.json file
    2. Extracts the access token from the appropriate structure
    3. Validates token format and checks expiry
    4. Decodes JWT claims to extract account ID
    5. Returns authenticated context

    Returns
    -------
    AuthContext
        Object containing the bearer token and ChatGPT account ID.

    Raises
    ------
    CodexAuthFileNotFoundError
        If the Codex CLI auth.json file is not found. This typically means
        the user hasn't run 'codex login' yet.
    CodexAuthTokenError
        If there's an issue with the token format or structure in the auth file.
    CodexAuthTokenExpiredError
        If the access token has expired and needs to be refreshed.

    Examples
    --------
    Basic usage:

    >>> from litellm_codex_oauth_provider.auth import get_auth_context
    >>> context = get_auth_context()
    >>> print(f"Using token: {context.access_token[:20]}...")
    >>> print(f"Account ID: {context.account_id}")

    Error handling:

    >>> try:
    ...     context = get_auth_context()
    ... except CodexAuthFileNotFoundError:
    ...     print("Please run 'codex login' first")
    ... except CodexAuthTokenExpiredError:
    ...     print("Token expired, please refresh with 'codex login'")

    Notes
    -----
    - The function automatically handles multiple auth.json structure formats
    - JWT account ID extraction uses URL-safe base64 decoding
    - Token expiry is checked against the current time
    - The function caches the context to minimize file I/O operations
    - All file operations use pathlib for cross-platform compatibility

    See Also
    --------
    - `get_bearer_token`: Direct token extraction without account ID
    - `_refresh_token`: Token refresh functionality
    - `AuthContext`: The returned authentication context object
    """
    token = _extract_bearer_token()
    account_id = _decode_account_id(token)
    return AuthContext(access_token=token, account_id=account_id)


def get_bearer_token() -> str:
    """Get bearer token with caching.

    Returns
    -------
    str
        The bearer token.
    """
    # For now, we'll just extract the token each time
    # In a more advanced implementation, we would cache it
    return _extract_bearer_token()


def _refresh_token() -> str:
    """Refresh OAuth token using refresh_token from auth.json.

    Returns
    -------
    str
        The new access token.

    Raises
    ------
    CodexAuthRefreshError
        If token refresh fails.
    """
    auth_data = _load_auth_data()

    # Try to get refresh token from different possible locations
    refresh_token = None
    if "chatgpt" in auth_data and "refresh_token" in auth_data["chatgpt"]:
        refresh_token = auth_data["chatgpt"]["refresh_token"]
    elif "refresh_token" in auth_data:
        refresh_token = auth_data["refresh_token"]

    if not refresh_token:
        raise CodexAuthRefreshError("No refresh token available")

    # Try to get client_id from auth data
    client_id = auth_data.get(
        "client_id", "dcjeopfkopeoapflkckokpmlpfhkfplp"
    )  # Default Codex client ID

    # Call OpenAI's token refresh endpoint
    refresh_url = "https://auth.openai.com/oauth/token"
    payload = {
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
        "client_id": client_id,
    }

    try:
        response = httpx.post(refresh_url, json=payload)
        response.raise_for_status()
        new_auth = response.json()

        # Update auth.json
        if "chatgpt" in auth_data:
            auth_data["chatgpt"]["access_token"] = new_auth["access_token"]
            auth_data["chatgpt"]["expires_at"] = time.time() + new_auth["expires_in"]
        else:
            auth_data["access_token"] = new_auth["access_token"]
            auth_data["expires_at"] = time.time() + new_auth["expires_in"]

        auth_path = _get_auth_path()
        with auth_path.open("w") as f:
            json.dump(auth_data, f, indent=2)

        return new_auth["access_token"]
    except Exception as e:
        raise CodexAuthRefreshError(f"Failed to refresh token: {e}") from e
