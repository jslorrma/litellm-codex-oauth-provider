"""Custom OpenAI clients for Codex authentication headers.

This module provides synchronous and asynchronous OpenAI client classes that handle
Codex-specific authentication headers and request preparation. The clients extend
the official OpenAI client library with Codex-specific customizations.

The client system includes:
- Custom header injection for Codex authentication
- Dynamic token provider pattern for OAuth tokens
- Account ID resolution from JWT claims
- Beta feature header management
- HTTP client configuration and timeout handling

Client Architecture
-------------------
1. **_BaseCodexClient**: Base class extending OpenAI client with custom headers
2. **CodexOpenAIClient**: Synchronous client for blocking operations
3. **AsyncCodexOpenAIClient**: Asynchronous client for non-blocking operations

Authentication Headers
----------------------
The clients automatically inject the following headers:
- `Authorization`: Bearer token from Codex CLI
- `OpenAI-Beta`: Experimental features flag
- `originator`: Client identification
- `chatgpt-account-id`: ChatGPT account identifier
- `Content-Type`: Request content type
- `Accept`: Response format preference

Examples
--------
Basic synchronous client usage:

>>> from litellm_codex_oauth_provider.openai_client import CodexOpenAIClient
>>> def get_token():
...     return "your_bearer_token_here"
>>> def get_account_id():
...     return "your_account_id_here"
>>> client = CodexOpenAIClient(
...     token_provider=get_token,
...     account_id_provider=get_account_id,
...     base_url="https://chatgpt.com/backend-api",
... )

Asynchronous client usage:

>>> from litellm_codex_oauth_provider.openai_client import AsyncCodexOpenAIClient
>>> async_client = AsyncCodexOpenAIClient(
...     token_provider=get_token,
...     account_id_provider=get_account_id,
...     base_url="https://chatgpt.com/backend-api",
... )

Custom header injection:

>>> class CustomCodexClient(CodexOpenAIClient):
...     def _prepare_options(self, options):
...         prepared = super()._prepare_options(options)
...         # Add custom headers
...         headers = httpx.Headers(prepared.headers or {})
...         headers["Custom-Header"] = "custom-value"
...         return prepared.copy(update={"headers": headers})

Notes
-----
- Clients use empty API key since authentication is handled via headers
- HTTP client is configurable for custom timeout and redirect settings
- Header injection happens during request preparation
- Both sync and async clients share the same authentication logic
- Token and account ID providers are called for each request

See Also
--------
- `CodexAuthProvider`: Main provider class using these clients
- `auth`: Authentication module for token management
- `constants`: Header names and values
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import httpx
from openai import AsyncOpenAI, OpenAI
from typing_extensions import override

from . import constants

if TYPE_CHECKING:
    from collections.abc import Callable

    from openai._base_client import FinalRequestOptions


def _create_http_client(base_url: str, timeout: float) -> httpx.Client:
    """Create a configured synchronous httpx client.

    Parameters
    ----------
    base_url : str
        Base URL for Codex API requests.
    timeout : float
        Request timeout in seconds.

    Returns
    -------
    httpx.Client
        HTTP client with redirects enabled.
    """
    return httpx.Client(base_url=base_url, timeout=timeout, follow_redirects=True)


def _create_async_http_client(base_url: str, timeout: float) -> httpx.AsyncClient:
    """Create a configured asynchronous httpx client.

    Parameters
    ----------
    base_url : str
        Base URL for Codex API requests.
    timeout : float
        Request timeout in seconds.

    Returns
    -------
    httpx.AsyncClient
        Async HTTP client with redirects enabled.
    """
    return httpx.AsyncClient(base_url=base_url, timeout=timeout, follow_redirects=True)


class _BaseCodexClient(OpenAI):
    """Base Codex-aware OpenAI client handling header injection.

    Parameters
    ----------
    token_provider : Callable[[], str]
        Callable returning a fresh bearer token.
    account_id_provider : Callable[[], str | None]
        Callable returning the ChatGPT account ID associated with the token.
    base_url : str
        Codex API base URL.
    timeout : float, optional
        Request timeout in seconds. Defaults to 60 seconds.
    http_client : httpx.Client | None, optional
        Optional pre-configured httpx client.
    **kwargs : Any
        Additional OpenAI client options.

    Notes
    -----
    - Uses an empty API key because authentication is performed via headers.
    - Header preparation occurs per-request to keep tokens fresh.
    """

    def __init__(
        self,
        *,
        token_provider: Callable[[], str],
        account_id_provider: Callable[[], str | None],
        base_url: str,
        timeout: float = 60.0,
        http_client: httpx.Client | None = None,
        **kwargs: Any,
    ) -> None:
        """Initialize the client with Codex-specific authentication providers."""
        client = http_client or _create_http_client(base_url, timeout)
        super().__init__(
            api_key="",
            base_url=base_url,
            timeout=timeout,
            http_client=client,
            **kwargs,
        )
        self._token_provider = token_provider
        self._account_id_provider = account_id_provider
        self._http_client = client

    @property
    def http_client(self) -> httpx.Client:
        """Return the underlying httpx client."""
        return self._http_client

    @property
    @override
    def auth_headers(self) -> dict[str, str]:
        """Return authorization headers built from the current token."""
        token = self._token_provider()
        if not token:
            return {}
        return {"Authorization": f"Bearer {token}"}

    @override
    def _prepare_options(self, options: FinalRequestOptions) -> FinalRequestOptions:
        """Inject Codex-required headers before dispatch.

        Parameters
        ----------
        options : FinalRequestOptions
            Base options prepared by the OpenAI client.

        Returns
        -------
        FinalRequestOptions
            Options updated with Authorization, beta, originator, content-type, accept,
            and account headers.
        """
        prepared = super()._prepare_options(options)
        headers = httpx.Headers(prepared.headers or {})

        token = self._token_provider()
        if token:
            headers["Authorization"] = f"Bearer {token}"
        headers.setdefault(constants.OPENAI_BETA_HEADER, constants.OPENAI_BETA_VALUE)
        headers.setdefault(constants.OPENAI_ORIGINATOR_HEADER, constants.OPENAI_ORIGINATOR_VALUE)
        headers.setdefault("Content-Type", "application/json")
        headers["Accept"] = headers.get("Accept") or "text/event-stream"

        account_id = self._account_id_provider() or ""
        if account_id:
            headers.setdefault(constants.CHATGPT_ACCOUNT_HEADER, account_id)

        return prepared.copy(update={"headers": headers})


class CodexOpenAIClient(_BaseCodexClient):
    """Sync Codex-aware OpenAI client.

    Notes
    -----
    Provides synchronous access to Codex `/responses` while handling authentication
    headers and content negotiation automatically.
    """


class AsyncCodexOpenAIClient(AsyncOpenAI):
    """Async Codex-aware OpenAI client.

    Notes
    -----
    Provides asynchronous access to Codex `/responses` while handling authentication
    headers and content negotiation automatically.
    """

    def __init__(
        self,
        *,
        token_provider: Callable[[], str],
        account_id_provider: Callable[[], str | None],
        base_url: str,
        timeout: float = 60.0,
        http_client: httpx.AsyncClient | None = None,
        **kwargs: Any,
    ) -> None:
        """Initialize the async client with Codex-specific authentication providers."""
        client = http_client or _create_async_http_client(base_url, timeout)
        super().__init__(
            api_key="",
            base_url=base_url,
            timeout=timeout,
            http_client=client,
            **kwargs,
        )
        self._token_provider = token_provider
        self._account_id_provider = account_id_provider
        self._http_client = client

    @property
    def http_client(self) -> httpx.AsyncClient:
        """Return the underlying async httpx client."""
        return self._http_client

    @property
    @override
    def auth_headers(self) -> dict[str, str]:
        """Return authorization headers built from the current token."""
        token = self._token_provider()
        if not token:
            return {}
        return {"Authorization": f"Bearer {token}"}

    @override
    async def _prepare_options(self, options: FinalRequestOptions) -> FinalRequestOptions:
        """Inject Codex-required headers before async dispatch.

        Parameters
        ----------
        options : FinalRequestOptions
            Base options prepared by the OpenAI client.

        Returns
        -------
        FinalRequestOptions
            Options updated with Authorization, beta, originator, content-type, accept,
            and account headers.
        """
        prepared = await super()._prepare_options(options)
        headers = httpx.Headers(prepared.headers or {})

        token = self._token_provider()
        if token:
            headers["Authorization"] = f"Bearer {token}"
        headers.setdefault(constants.OPENAI_BETA_HEADER, constants.OPENAI_BETA_VALUE)
        headers.setdefault(constants.OPENAI_ORIGINATOR_HEADER, constants.OPENAI_ORIGINATOR_VALUE)
        headers.setdefault("Content-Type", "application/json")
        headers["Accept"] = headers.get("Accept") or "text/event-stream"

        account_id = self._account_id_provider() or ""
        if account_id:
            headers.setdefault(constants.CHATGPT_ACCOUNT_HEADER, account_id)

        return prepared.copy(update={"headers": headers})
