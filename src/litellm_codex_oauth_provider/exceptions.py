"""Custom exceptions for the LiteLLM Codex OAuth Provider."""

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
