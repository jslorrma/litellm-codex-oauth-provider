"""LiteLLM Codex OAuth Provider.

A custom provider for LiteLLM that bridges Codex CLI OAuth authentication
to OpenAI-compatible APIs.
"""

from __future__ import annotations

from ._version import __version__
from .exceptions import (
    CodexAuthError,
    CodexAuthFileNotFoundError,
    CodexAuthRefreshError,
    CodexAuthTokenError,
    CodexAuthTokenExpiredError,
)
from .provider import CodexAuthProvider


# Import provider only when needed to avoid dependency issues
def get_provider() -> type[CodexAuthProvider]:
    """Get the CodexAuthProvider class.

    This function imports the provider module only when needed to avoid
    dependency issues during installation.
    """
    return CodexAuthProvider


# Instantiate the provider
codex_auth_provider = CodexAuthProvider()

__all__ = [
    "CodexAuthError",
    "CodexAuthFileNotFoundError",
    "CodexAuthProvider",
    "CodexAuthRefreshError",
    "CodexAuthTokenError",
    "CodexAuthTokenExpiredError",
    "__version__",
    "codex_auth_provider",
    "get_provider",
]
