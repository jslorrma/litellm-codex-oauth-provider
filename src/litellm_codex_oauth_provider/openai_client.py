"""Custom OpenAI clients for Codex authentication headers.

This module provides synchronous and asynchronous OpenAI client classes that handle Codex authentication.
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
    return httpx.Client(base_url=base_url, timeout=timeout, follow_redirects=True)


def _create_async_http_client(base_url: str, timeout: float) -> httpx.AsyncClient:
    return httpx.AsyncClient(base_url=base_url, timeout=timeout, follow_redirects=True)


class _BaseCodexClient(OpenAI):
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
        token = self._token_provider()
        if not token:
            return {}
        return {"Authorization": f"Bearer {token}"}

    @override
    def _prepare_options(self, options: FinalRequestOptions) -> FinalRequestOptions:
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
    """Sync Codex-aware OpenAI client."""


class AsyncCodexOpenAIClient(AsyncOpenAI):
    """Async Codex-aware OpenAI client."""

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
        token = self._token_provider()
        if not token:
            return {}
        return {"Authorization": f"Bearer {token}"}

    @override
    async def _prepare_options(self, options: FinalRequestOptions) -> FinalRequestOptions:
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
