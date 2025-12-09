"""Custom exceptions for the LiteLLM Codex OAuth Provider.

This module defines a hierarchy of custom exceptions for handling various error
conditions that may occur during Codex authentication and API operations.

The exception hierarchy provides:
- Base exception for all Codex-related errors
- Specific exceptions for different error categories
- Detailed error messages with actionable guidance
- Proper exception chaining for debugging

Exception Hierarchy
-------------------
- **CodexAuthError**: Base exception for all authentication errors
  - **CodexAuthFileNotFoundError**: Auth file missing
  - **CodexAuthTokenError**: General token issues
    - **CodexAuthTokenExpiredError**: Token has expired
  - **CodexAuthRefreshError**: Token refresh failure

Error Categories
----------------
- **File System**: Missing or inaccessible auth files
- **Token Validation**: Invalid, expired, or malformed tokens
- **Network Issues**: API connectivity and timeout problems
- **Authentication Flow**: OAuth process failures
"""

from __future__ import annotations


class CodexAuthError(Exception):
    """Base exception for Codex authentication errors."""


class CodexAuthFileNotFoundError(CodexAuthError):
    """Raised when the Codex auth file is not found."""


class CodexAuthTokenError(CodexAuthError):
    """Raised when there's an issue with the Codex auth token."""


class CodexAuthTokenExpiredError(CodexAuthTokenError):
    """Raised when the Codex auth token has expired."""


class CodexAuthRefreshError(CodexAuthError):
    """Raised when token refresh fails."""
