"""Simple HTTP client wrapper for Codex API requests.

This module provides a lightweight httpx wrapper that handles Codex-specific
request formatting and response parsing. It focuses on the core functionality
needed for reliable API communication without complex abstractions.

Key Features:
- Authentication header injection
- SSE response handling
- Basic error handling
- Simple sync/async interfaces
- Clean separation from OpenAI client logic
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

import httpx

from . import constants
from .sse_utils import parse_sse_events

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Mapping


class CodexAPIClient:
    """Simple HTTP client for Codex API requests using httpx.

    This client handles the actual HTTP communication with the Codex API,
    focusing on reliability and simplicity while supporting both sync and
    async operations.

    Examples
    --------
    Basic usage:

    >>> client = SimpleCodexClient(
    ...     token_provider=lambda: "bearer_token_here",
    ...     account_id_provider=lambda: "account_id_here",
    ... )
    >>> response = client.post_responses({"model": "gpt-5.1-codex", "input": [...]})

    Async usage:

    >>> async_client = SimpleCodexClient(
    ...     token_provider=lambda: "bearer_token_here",
    ...     account_id_provider=lambda: "account_id_here",
    ... )
    >>> response = await async_client.post_responses_async(
    ...     {"model": "gpt-5.1-codex", "input": [...]}
    ... )
    """

    def __init__(
        self,
        token_provider: callable,
        account_id_provider: callable | None = None,
        base_url: str | None = None,
        timeout: float = 60.0,
    ) -> None:
        """Initialize the simple Codex client.

        Parameters
        ----------
        token_provider : callable
            Function that returns the current bearer token
        account_id_provider : callable | None
            Function that returns the ChatGPT account ID
        base_url : str | None
            Base URL for the Codex API
        timeout : float
            Request timeout in seconds
        """
        self.token_provider = token_provider
        self.account_id_provider = account_id_provider or (lambda: None)
        self.base_url = base_url or constants.CODEX_API_BASE_URL
        self.timeout = timeout

        # Create sync and async httpx clients
        self._sync_client = httpx.Client(timeout=self.timeout)
        self._async_client = httpx.AsyncClient(timeout=self.timeout)

    def _build_headers(self) -> dict[str, str]:
        """Build essential headers for Codex API requests."""
        headers = {
            "Accept": "text/event-stream",
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.token_provider()}",
            constants.OPENAI_BETA_HEADER: constants.OPENAI_BETA_VALUE,
            constants.OPENAI_ORIGINATOR_HEADER: constants.OPENAI_ORIGINATOR_VALUE,
        }

        # Add account ID if available
        account_id = self.account_id_provider()
        if account_id:
            headers[constants.CHATGPT_ACCOUNT_HEADER] = account_id

        return headers

    def post_responses(
        self,
        payload: Mapping[str, Any],
        url_suffix: str = "/responses",
    ) -> dict[str, Any]:
        """Post to the Codex responses endpoint and parse response.

        Parameters
        ----------
        payload : Mapping[str, Any]
            Request payload for the responses endpoint
        url_suffix : str
            URL suffix to append to base URL

        Returns
        -------
        dict[str, Any]
            Parsed response data

        Raises
        ------
        httpx.HTTPStatusError
            If the API returns an error status code
        """
        url = f"{self.base_url.rstrip('/')}{url_suffix}"
        headers = self._build_headers()

        # Ensure stream is enabled
        payload_with_stream = dict(payload)
        payload_with_stream.setdefault("stream", True)

        try:
            response = self._sync_client.post(
                url,
                json=payload_with_stream,
                headers=headers,
            )
            response.raise_for_status()
            return self._parse_response(response)

        except httpx.HTTPStatusError as exc:
            # Let HTTP errors bubble up with context
            raise exc
        except Exception as exc:
            # Wrap other exceptions for clarity
            raise RuntimeError(f"Failed to communicate with Codex API: {exc}") from exc

    async def post_responses_async(
        self,
        payload: Mapping[str, Any],
        url_suffix: str = "/responses",
    ) -> dict[str, Any]:
        """Async version of post_responses.

        Parameters and returns follow the same pattern as post_responses().
        """
        url = f"{self.base_url.rstrip('/')}{url_suffix}"
        headers = self._build_headers()

        # Ensure stream is enabled
        payload_with_stream = dict(payload)
        payload_with_stream.setdefault("stream", True)

        try:
            response = await self._async_client.post(
                url,
                json=payload_with_stream,
                headers=headers,
            )
            response.raise_for_status()
            return await self._parse_response_async(response)

        except httpx.HTTPStatusError as exc:
            # Let HTTP errors bubble up with context
            raise exc
        except Exception as exc:
            # Wrap other exceptions for clarity
            raise RuntimeError(f"Failed to communicate with Codex API: {exc}") from exc

    async def stream_responses_sse(
        self,
        payload: Mapping[str, Any],
        url_suffix: str = "/responses",
    ) -> AsyncIterator[dict[str, Any]]:
        """Stream responses from Codex API with full SSE parsing.

        This method performs a streaming request and yields individual SSE events
        as they are received from the API. Each event is parsed and yielded as
        a structured dictionary.

        Parameters
        ----------
        payload : Mapping[str, Any]
            Request payload for the responses endpoint
        url_suffix : str
            URL suffix to append to base URL

        Yields
        ------
        dict[str, Any]
            Parsed SSE events as structured dictionaries

        Raises
        ------
        httpx.HTTPStatusError
            If the API returns an error status code

        Examples
        --------
        >>> async for event in client.stream_responses_sse(payload):
        ...     print(f"Event: {event['type']}")
        """
        url = f"{self.base_url.rstrip('/')}{url_suffix}"
        headers = self._build_headers()

        # Ensure stream is enabled
        payload_with_stream = dict(payload)
        payload_with_stream.setdefault("stream", True)

        try:
            async with self._async_client.stream(
                "POST",
                url,
                json=payload_with_stream,
                headers=headers,
            ) as response:
                response.raise_for_status()
                async for event in parse_sse_events(response):
                    yield event

        except httpx.HTTPStatusError as exc:
            # Let HTTP errors bubble up with context
            raise exc
        except Exception as exc:
            # Wrap other exceptions for clarity
            raise RuntimeError(f"Failed to communicate with Codex API: {exc}") from exc

    def _parse_response(self, response: httpx.Response) -> dict[str, Any]:
        """Parse response handling both JSON and SSE formats.

        Parameters
        ----------
        response : httpx.Response
            HTTP response from the API

        Returns
        -------
        dict[str, Any]
            Parsed response data
        """
        content_type = (response.headers.get("content-type") or "").lower()
        body_text = response.text

        # Handle SSE (Server-Sent Events) format
        if "text/event-stream" in content_type or body_text.lstrip().startswith("event:"):
            return self._parse_sse_response(body_text)

        # Handle regular JSON response
        try:
            return response.json()
        except json.JSONDecodeError as exc:
            raise RuntimeError("Codex API returned invalid JSON response") from exc

    async def _parse_response_async(self, response: httpx.Response) -> dict[str, Any]:
        """Async version of _parse_response."""
        return self._parse_response(response)

    def _parse_sse_response(self, sse_text: str) -> dict[str, Any]:
        """Parse SSE text into final response data.

        Parameters
        ----------
        sse_text : str
            SSE-formatted text from the API

        Returns
        -------
        dict[str, Any]
            Extracted response data
        """
        events = []
        current_data = ""

        for line in sse_text.splitlines():
            stripped_line = line.strip()

            if stripped_line.startswith("data:"):
                current_data = stripped_line[5:].strip()

                if not current_data or current_data == "[DONE]":
                    continue

                try:
                    event = json.loads(current_data)
                    events.append(event)
                except json.JSONDecodeError:
                    # Skip invalid JSON lines
                    continue

        # Find the final response event
        for event in reversed(events):
            if event.get("type") in {"response.done", "response.completed"}:
                response_payload = event.get("response") or event.get("data")
                if isinstance(response_payload, dict):
                    return response_payload

            # Fallback: look for response in the event
            if "response" in event and isinstance(event["response"], dict):
                return event["response"]

        # If no response found, return the last event as fallback
        if events:
            return events[-1] if isinstance(events[-1], dict) else {}

        raise RuntimeError("No response data found in SSE stream")

    def close(self) -> None:
        """Close the HTTP client connections."""
        self._sync_client.close()

    async def aclose(self) -> None:
        """Close the async HTTP client connections."""
        await self._async_client.aclose()

    def __enter__(self) -> CodexAPIClient:
        """Context manager entry."""
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: BaseException | None,
    ) -> None:
        """Context manager exit."""
        self.close()

    async def __aenter__(self) -> CodexAPIClient:
        """Async context manager entry."""
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: BaseException | None,
    ) -> None:
        """Async context manager exit."""
        await self.aclose()
