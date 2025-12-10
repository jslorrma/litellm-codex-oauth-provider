"""Async SSE parsing tests ensure async iter_lines is supported."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from litellm_codex_oauth_provider.sse_utils import parse_sse_events

if TYPE_CHECKING:
    from collections.abc import AsyncIterator


class _AsyncLineResponse:
    """Minimal async response stub with aiter_lines for SSE parsing."""

    def __init__(self, lines: list[bytes]) -> None:
        self.headers = {"content-type": "text/event-stream"}
        self._lines = lines

    async def iter_lines(self) -> AsyncIterator[bytes]:
        for line in self._lines:
            yield line

    async def aiter_lines(self) -> AsyncIterator[str]:
        for line in self._lines:
            yield line.decode("utf-8")


def test_parse_sse_events_handles_async_iter_lines() -> None:
    """parse_sse_events yields events from async iter_lines responses."""
    lines = [
        b"event: text",
        b'data: {"type": "text_delta", "content": "hi"}',
        b"",
        b"data: [DONE]",
        b"",
    ]

    response = _AsyncLineResponse(lines)

    async def collect() -> list[str]:
        seen = []
        async for event in parse_sse_events(response):
            seen.append(event["type"])
        return seen

    event_types = asyncio.run(collect())
    assert event_types == ["text_delta", "done"]
