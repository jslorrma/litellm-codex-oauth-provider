"""Custom OpenAI clients that inject Codex authentication headers."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

import httpx
from openai import AsyncOpenAI, OpenAI
from typing_extensions import override

from . import constants

if TYPE_CHECKING:
    from collections.abc import Callable

    from openai._base_client import FinalRequestOptions


logger = logging.getLogger(__name__)


def _bootstrap_cf_cookies(base_url: str, timeout: float) -> httpx.Cookies:
    """Warm Cloudflare cookies to avoid HTML challenges."""
    cookies = httpx.Cookies()
    headers = {
        "Origin": "https://chatgpt.com",
        "Referer": "https://chatgpt.com/",
    }
    try:
        with httpx.Client(
            base_url=base_url,
            headers=headers,
            timeout=timeout,
            follow_redirects=True,
        ) as client:
            for path in ("", "responses"):
                try:
                    client.get(path or "/", timeout=timeout)
                except Exception:
                    continue
            cookies.update(client.cookies)
    except Exception:  # pragma: no cover - diagnostic only
        logger.debug("Cloudflare preflight failed; continuing without cookies", exc_info=True)
    return cookies


def _create_http_client(base_url: str, timeout: float) -> httpx.Client:
    cookies = _bootstrap_cf_cookies(base_url, timeout)
    return httpx.Client(
        base_url=base_url,
        timeout=timeout,
        follow_redirects=True,
        cookies=cookies,
    )


def _create_async_http_client(base_url: str, timeout: float) -> httpx.AsyncClient:
    cookies = _bootstrap_cf_cookies(base_url, timeout)
    return httpx.AsyncClient(
        base_url=base_url,
        timeout=timeout,
        follow_redirects=True,
        cookies=cookies,
    )


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
        headers.setdefault("Accept-Language", constants.BROWSER_ACCEPT_LANGUAGE)
        headers.setdefault("Origin", "https://chatgpt.com")
        headers.setdefault("Referer", "https://chatgpt.com/")
        try:
            cookie_header = "; ".join(
                f"{name}={value}" for name, value in self._client.cookies.items()
            )
        except Exception:
            cookie_header = ""
        if cookie_header:
            headers["Cookie"] = cookie_header

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
        headers.setdefault("Accept-Language", constants.BROWSER_ACCEPT_LANGUAGE)
        headers.setdefault("Origin", "https://chatgpt.com")
        headers.setdefault("Referer", "https://chatgpt.com/")
        try:
            cookie_header = "; ".join(
                f"{name}={value}" for name, value in self._client.cookies.items()
            )
        except Exception:
            cookie_header = ""
        if cookie_header:
            headers["Cookie"] = cookie_header

        account_id = self._account_id_provider() or ""
        if account_id:
            headers.setdefault(constants.CHATGPT_ACCOUNT_HEADER, account_id)

        return prepared.copy(update={"headers": headers})
