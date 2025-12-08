"""LiteLLM Codex OAuth Provider.

A custom provider for LiteLLM that bridges Codex CLI OAuth authentication
to OpenAI-compatible APIs, enabling access to ChatGPT Plus models through
the official OpenAI client library.

This package provides a complete solution for integrating Codex CLI authentication
with LiteLLM, including automatic token management, model normalization, response
adaptation, and comprehensive error handling.

Quick Start
-----------
1. Install the package: ``pip install litellm-codex-oauth-provider``
2. Authenticate with Codex CLI: ``codex login``
3. Use with LiteLLM:

   >>> import litellm
   >>> from litellm_codex_oauth_provider import CodexAuthProvider
   >>> # Register the provider
   >>> litellm.register_provider("codex", CodexAuthProvider())
   >>> # Make requests
   >>> response = litellm.completion(
   ...     model="codex/gpt-5.1-codex-max", messages=[{"role": "user", "content": "Hello"}]
   ... )

Features
--------
- **OAuth Integration**: Seamless Codex CLI authentication
- **Model Support**: Full GPT-5.1 Codex model family support
- **Tool Calling**: Complete OpenAI tool schema compatibility
- **Streaming**: Server-Sent Events with fallback mechanisms
- **Async Support**: Full asynchronous operation support
- **Error Handling**: Comprehensive error handling and diagnostics
- **Caching**: Intelligent token and instruction caching

Supported Models
----------------
- ``gpt-5.1-codex``: Standard Codex model
- ``gpt-5.1-codex-max``: High-capability reasoning model
- ``gpt-5.1-codex-mini``: Efficient, fast model
- ``gpt-5.1``: Base GPT-5.1 model

With effort levels: ``-none``, ``-minimal``, ``-low``, ``-medium``, ``-high``, ``-xhigh``

Examples
--------
Basic usage:

>>> from litellm_codex_oauth_provider import CodexAuthProvider
>>> provider = CodexAuthProvider()
>>> response = provider.completion(
...     model="codex/gpt-5.1-codex",
...     messages=[{"role": "user", "content": "Explain quantum computing"}],
... )

With tools:

>>> tools = [
...     {
...         "type": "function",
...         "function": {
...             "name": "get_weather",
...             "description": "Get weather information",
...             "parameters": {"type": "object", "properties": {"location": {"type": "string"}}},
...         },
...     }
... ]
>>> response = provider.completion(
...     model="codex/gpt-5.1-codex-max",
...     messages=[{"role": "user", "content": "What's the weather?"}],
...     tools=tools,
... )

Async usage:

>>> import asyncio
>>> async def main():
...     provider = CodexAuthProvider()
...     response = await provider.acompletion(
...         model="codex/gpt-5.1-codex", messages=[{"role": "user", "content": "Hello"}]
...     )
...     return response
>>> # asyncio.run(main())

Configuration
-------------
Environment variables:
- ``CODEX_AUTH_FILE``: Custom auth file path
- ``CODEX_CACHE_DIR``: Custom cache directory
- ``CODEX_DEBUG``: Enable debug logging

Notes
-----
- Requires Codex CLI authentication (``codex login``)
- Automatically handles token refresh and caching
- Compatible with LiteLLM proxy configurations
- Provides detailed logging when CODEX_DEBUG=1
- Thread-safe for concurrent usage

See Also
--------
- `CodexAuthProvider`: Main provider class
- `exceptions`: Custom exception classes
- LiteLLM documentation: https://docs.litellm.ai/
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
