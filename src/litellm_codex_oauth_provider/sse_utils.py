"""SSE utilities for parsing Codex API streaming responses."""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, Any, NotRequired, TypedDict

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    import httpx


logger = logging.getLogger(__name__)


class SSEEvent(TypedDict, total=False):
    """Standardized SSE event structure."""

    type: str
    raw_type: str | None
    data: Any
    id: str | None
    delta: NotRequired[str | None]
    item_id: NotRequired[str | None]
    finish_reason: NotRequired[str | None]
    usage: NotRequired[dict[str, Any] | None]


_TEXT_EVENT_TYPES = {
    "text",
    "text.delta",
    "text_delta",
    "response.output_text.delta",
    "response.output_text.delta.partial",
}
_REASONING_EVENT_TYPES = {
    "response.reasoning_summary_text.delta",
    "response.reasoning_text.delta",
}
_FUNCTION_ARGUMENTS_TYPES = {
    "function_call.arguments.delta",
    "function_call_arguments",
    "function_call",
    "response.function_call_arguments.delta",
}
_COMPLETION_EVENT_TYPES = {"response.done", "response.completed", "completed", "response"}


def _extract_delta(payload: Any) -> str | None:
    if isinstance(payload, str):
        return payload
    if not isinstance(payload, dict):
        return None

    for key in ("delta", "content", "text", "arguments"):
        value = payload.get(key)
        if isinstance(value, str):
            return value
    if isinstance(payload.get("part"), dict):
        nested = payload["part"].get("text")
        if isinstance(nested, str):
            return nested
    return None


def _extract_usage_and_finish(payload: Any) -> tuple[dict[str, Any] | None, str | None]:
    if not isinstance(payload, dict):
        return None, None

    usage = payload.get("usage")
    finish_reason = payload.get("finish_reason")

    if isinstance(payload.get("response"), dict):
        response = payload["response"]
        usage = usage or response.get("usage")
        finish_reason = finish_reason or response.get("finish_reason")

    return usage if isinstance(usage, dict) else None, finish_reason


def _resolve_raw_type(event_type: str | None, data: Any) -> str | None:
    if event_type:
        return event_type
    if isinstance(data, dict):
        data_type = data.get("type")
        if isinstance(data_type, str):
            return data_type
    return None


def _resolve_normalized_type(raw_type: str | None) -> str:
    if raw_type in _TEXT_EVENT_TYPES:
        return "text_delta"
    if raw_type in _REASONING_EVENT_TYPES:
        return "reasoning_delta"
    if raw_type in _FUNCTION_ARGUMENTS_TYPES:
        return "function_arguments_delta"
    if raw_type in _COMPLETION_EVENT_TYPES:
        return "completion"
    return raw_type or "unknown"


def _attach_delta_metadata(event: SSEEvent, data: Any, normalized_type: str) -> None:
    if normalized_type not in {"text_delta", "reasoning_delta", "function_arguments_delta"}:
        return

    delta = _extract_delta(data)
    if delta is not None:
        event["delta"] = delta
    if isinstance(data, dict):
        item_id = data.get("item_id") or data.get("item", {}).get("id")
        if item_id:
            event["item_id"] = item_id


def _attach_completion_metadata(event: SSEEvent, data: Any, normalized_type: str) -> None:
    if normalized_type != "completion":
        return

    usage, finish_reason = _extract_usage_and_finish(data)
    event["usage"] = usage
    event["finish_reason"] = finish_reason


def _normalize_event(
    event_type: str | None, data: Any, event_id: str | None = None
) -> SSEEvent | None:
    if data is None or (isinstance(data, str) and not data.strip()):
        return None

    raw_type = _resolve_raw_type(event_type, data)

    if isinstance(data, str) and data.strip() == "[DONE]":
        return SSEEvent(type="done", raw_type=raw_type, data=None, id=event_id)

    normalized_type = _resolve_normalized_type(raw_type)

    event: SSEEvent = {
        "type": normalized_type,
        "raw_type": raw_type,
        "data": data,
        "id": event_id,
    }

    _attach_delta_metadata(event, data, normalized_type)
    _attach_completion_metadata(event, data, normalized_type)

    if normalized_type == "unknown":
        logger.debug("Unhandled SSE event type", extra={"event_type": raw_type, "data": data})

    return event


async def parse_sse_events(response: httpx.Response) -> AsyncIterator[SSEEvent]:  # noqa: C901
    """Parse SSE response into structured events.

    Parameters
    ----------
    response : httpx.Response
        HTTP response with text/event-stream content

    Yields
    ------
    SSEEvent
        Structured SSE events with type, data, and optional ID

    Examples
    --------
    >>> async for event in parse_sse_events(response):
    ...     print(f"Event: {event['type']}, Data: {event['data']}")
    """
    # if response.headers.get("content-type", "").lower() != "text/event-stream":
    #     raise ValueError("Response is not SSE format")

    event_type: str | None = None
    event_id: str | None = None
    data_lines: list[str] = []

    async def _flush() -> AsyncIterator[SSEEvent]:
        nonlocal event_type, event_id, data_lines
        if data_lines:
            data_block = "\n".join(data_lines).strip()
            parsed_data: Any = data_block
            try:
                parsed_data = json.loads(data_block)
            except json.JSONDecodeError:
                parsed_data = data_block

            event = _normalize_event(event_type, parsed_data, event_id)
            event_type = None
            event_id = None
            data_lines = []
            if event:
                yield event

    # httpx Response has aiter_lines for async line iteration
    async for raw_line in response.aiter_lines():
        # raw_line is always str in aiter_lines
        line_chunks = raw_line.split("\n")

        for line in line_chunks:
            if line == "":
                async for event in _flush():
                    yield event
                continue

            if not line:
                continue

            if line.startswith("event:"):
                event_type = line[6:].strip()
            elif line.startswith("data:"):
                data_content = line[5:].strip()
                data_lines.append(data_content)
            elif line.startswith("id:"):
                event_id = line[3:].strip()

    async for event in _flush():
        yield event


def extract_text_from_sse_event(event: SSEEvent) -> str | None:
    """Extract text content from SSE event if it's a text delta.

    Parameters
    ----------
    event : SSEEvent
        SSE event to extract text from

    Returns
    -------
    str | None
        Text content or None if not a text event
    """
    if event["type"] != "text_delta":
        return None

    if isinstance(event.get("delta"), str):
        return event["delta"]

    data = event.get("data")
    if isinstance(data, dict):
        for key in ("content", "text", "delta"):
            value = data.get(key)
            if isinstance(value, str):
                return value
    elif isinstance(data, str):
        try:
            parsed = json.loads(data)
            return parsed.get("content", "") or parsed.get("text", "")
        except (json.JSONDecodeError, AttributeError):
            return data
    return None


def extract_tool_call_from_sse_event(event: SSEEvent) -> dict[str, Any] | None:
    """Extract tool call information from SSE event.

    Parameters
    ----------
    event : SSEEvent
        SSE event to extract tool call from

    Returns
    -------
    dict[str, Any] | None
        Tool call information or None if not a tool call event
    """
    if event["type"] != "function_arguments_delta":
        return None

    data = event.get("data")
    if isinstance(data, str):
        try:
            data = json.loads(data)
        except json.JSONDecodeError:
            data = {"arguments": event.get("delta", data)}

    if not isinstance(data, dict):
        return None

    arguments = data.get("arguments") or data.get("delta") or event.get("delta") or ""
    call_id = data.get("call_id") or data.get("id") or event.get("item_id")
    name = data.get("name")
    if isinstance(data.get("function"), dict):
        name = name or data["function"].get("name")

    return {
        "call_id": call_id,
        "arguments": arguments if isinstance(arguments, str) else "",
        "name": name,
    }
