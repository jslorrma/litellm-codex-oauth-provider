r"""Codex response adapters for LiteLLM interoperability.

This module converts Codex `/responses` payloads—whether delivered as Server-Sent Events
(SSE) buffers or plain JSON bodies—into LiteLLM `ModelResponse` objects. Functions are
intentionally side-effect free to keep sync and async call stacks simple and testable.
Whenever possible, parsing relies on OpenAI's typed models for strict validation, while
fallback paths preserve resilience against minor API drift or incomplete payloads.

Key capabilities
----------------
- Detect SSE buffers versus JSON responses and normalize them into a single payload
- Validate payloads with OpenAI typed models and surface concise debug context on failure
- Normalize tool calls from message-level or output-level formats
- Build LiteLLM usage blocks from Codex token counters and inferred totals
- Generate minimal streaming chunks to simulate streaming from completed responses

Examples
--------
Parse a JSON response:

>>> from litellm_codex_oauth_provider.adapter import transform_response
>>> payload = {
...     "id": "1",
...     "choices": [
...         {"index": 0, "message": {"role": "assistant", "content": "hi"}, "finish_reason": "stop"}
...     ],
... }
>>> transform_response(payload, model="gpt-5.1-codex").choices[0].message.content
'hi'

Convert buffered SSE to JSON:

>>> from litellm_codex_oauth_provider.adapter import convert_sse_to_json
>>> sse = 'data: {"type": "response.done", "response": {"id": "1", "choices": [{"index": 0, "message": {"role": "assistant", "content": "hi"}}]}}\\n'
>>> convert_sse_to_json(sse)["choices"][0]["message"]["content"]
'hi'

Generate a streaming chunk from a completed response:

>>> from litellm_codex_oauth_provider.adapter import build_streaming_chunk
>>> model_response = transform_response(payload, model="gpt-5.1-codex")
>>> chunk = build_streaming_chunk(model_response)
>>> chunk.is_finished
True

Notes
-----
- Logging is emitted at DEBUG level only to avoid noisy output.
- All helpers are deterministic and reusable across sync/async provider paths.
- Tool-call handling supports both modern and legacy Codex formats.
- Usage aggregation tolerates missing totals by deriving them from known fields.

See Also
--------
- `litellm.types.utils.GenericStreamingChunk`: Streaming response chunk used by LiteLLM
- `litellm.ModelResponse`: Normalized response structure expected by LiteLLM
- `openai.types.responses.Response`: Typed model used for validation
"""

from __future__ import annotations

import json
import logging
import time
from collections.abc import Mapping
from typing import TYPE_CHECKING, Any

from litellm import Choices, Message, ModelResponse
from litellm.types.utils import GenericStreamingChunk, Usage

if TYPE_CHECKING:
    import httpx


logger = logging.getLogger(__name__)


def parse_response_body(response: httpx.Response) -> dict[str, Any]:
    """Return JSON payload from Codex response, handling buffered SSE.

    This function parses HTTP responses from the Codex API, handling both standard
    JSON responses and Server-Sent Events (SSE) streams. It automatically detects
    the response type and applies the appropriate parsing strategy.

    The parsing process:
    1. Checks Content-Type header and body text for SSE detection
    2. For SSE: Converts buffered text to final JSON payload
    3. For JSON: Directly parses as JSON

    Parameters
    ----------
    response : httpx.Response
        The HTTP response object from the Codex API request.

    Returns
    -------
    dict[str, Any]
        Parsed JSON payload from the response.

    Raises
    ------
    RuntimeError
        If the response cannot be parsed as valid JSON or if SSE stream
        doesn't contain a final response event.

    Examples
    --------
    Standard JSON response:

    >>> import httpx
    >>> response = httpx.get("https://api.example.com/endpoint")
    >>> data = parse_response_body(response)
    >>> print(data["choices"][0]["message"]["content"])

    SSE response handling:

    >>> # Response with Content-Type: text/event-stream
    >>> response = httpx.get("https://api.example.com/stream")
    >>> data = parse_response_body(response)
    >>> print(data["response"]["choices"][0]["message"]["content"])

    Notes
    -----
    - SSE detection is based on Content-Type header and "data:" prefix check
    - Direct JSON parsing for non-SSE responses
    - SSE processing extracts the final response event from buffered text

    See Also
    --------
    - `convert_sse_to_json`: Convert SSE text to JSON
    - `transform_response`: Transform response to LiteLLM format
    """
    content_type = (response.headers.get("content-type") or "").lower()
    body_text = response.text
    # Check for SSE by content-type header or "data:" prefix (SSE format)
    if "text/event-stream" in content_type or body_text.lstrip().startswith("data:"):
        parsed = convert_sse_to_json(body_text)
        if parsed:
            return parsed
        raise RuntimeError("Codex API returned stream without final response event")
    
    # Parse as standard JSON response
    try:
        return response.json()
    except json.JSONDecodeError as exc:
        raise RuntimeError("Codex API returned invalid JSON") from exc


def convert_sse_to_json(payload: str) -> dict[str, Any]:
    r"""Convert buffered SSE text to final JSON payload.

    Parameters
    ----------
    payload : str
        Concatenated SSE buffer containing `data:` lines.

    Returns
    -------
    dict[str, Any]
        Parsed response payload extracted from SSE events. Empty dict if no usable event
        is found.

    Raises
    ------
    RuntimeError
        If no valid response events are found in the SSE payload.

    Examples
    --------
    Basic SSE conversion:

    >>> sse_text = 'data: {"response": {"choices": [...]}}\\ndata: [DONE]'
    >>> result = convert_sse_to_json(sse_text)
    >>> print(result["response"]["choices"][0]["message"]["content"])

    Multi-event SSE:

    >>> sse_text = '''data: {"type": "progress", "status": "processing"}
    ... data: {"response": {"choices": [{"message": {"content": "Hello"}}]}}
    ... data: [DONE]'''
    >>> result = convert_sse_to_json(sse_text)
    >>> print(result["response"]["choices"][0]["message"]["content"])

    Notes
    -----
    - SSE format: Each event starts with "data:" followed by JSON content
    - Completion marker: "[DONE]" indicates end of stream
    - Direct extraction: Searches for response payloads in completion events
    - Error handling: Skips invalid JSON events and continues processing
    - Event order: Processes events in reverse to find final response

    See Also
    --------
    - `_extract_response_from_events`: Response payload extraction
    - `parse_response_body`: Higher-level response parsing
    """
    events: list[dict[str, Any]] = []
    for line in payload.splitlines():
        if not line.startswith("data:"):
            continue
        data = line.removeprefix("data:").strip()
        if not data or data == "[DONE]":
            continue
        try:
            event = json.loads(data)
        except json.JSONDecodeError:
            continue
        if isinstance(event, Mapping):
            events.append(event)

    return _extract_response_from_events(events)


def transform_response(openai_response: dict[str, Any], model: str) -> ModelResponse:
    """Transform OpenAI API response to LiteLLM ModelResponse format.

    This function converts raw responses from the Codex backend API into LiteLLM-compatible
    ModelResponse objects. It handles multiple response formats, extracts tool calls,
    normalizes usage statistics, and creates a standardized response structure.

    The transformation process:
    1. Extracts response payload from various possible locations in the response
    2. Handles missing choices by coercing from output field when available
    3. Extracts and normalizes tool calls from multiple response formats
    4. Resolves message content and role information with fallbacks
    5. Builds usage statistics from available token information
    6. Creates complete ModelResponse with all required fields and metadata

    Parameters
    ----------
    openai_response : dict[str, Any]
        Raw response from OpenAI/Codex API in various possible formats including
        direct responses, nested response objects, or legacy structures.
    model : str
        Model identifier used for the request, included in response for reference.

    Returns
    -------
    ModelResponse
        LiteLLM-compatible response object with choices, usage, model info, and metadata.

    Raises
    ------
    RuntimeError
        If response is missing required choices output or cannot be parsed.
    """
    response_payload = openai_response.get("response", openai_response)
    usage_payload = response_payload.get("usage") or openai_response.get("usage")
    choices = response_payload.get("choices")

    if not choices and "output" in response_payload:
        choices = _coerce_choices_from_output(response_payload.get("output"))

    if not choices:
        raise RuntimeError("Codex API response is missing choices output")

    primary_choice = choices[0]
    message_payload = primary_choice.get("message") or {}
    tool_calls = _collect_tool_calls(message_payload, response_payload)
    message_content, message_role = _resolve_message_content(
        message_payload, response_payload, tool_calls
    )
    function_call = _coerce_function_call(message_payload)
    system_fingerprint = response_payload.get("system_fingerprint") or openai_response.get(
        "system_fingerprint"
    )
    finish_reason = _resolve_finish_reason(primary_choice, tool_calls)
    created = response_payload.get("created") or response_payload.get("created_at")

    return ModelResponse(
        id=response_payload.get("id") or openai_response.get("id", ""),
        choices=[
            Choices(
                finish_reason=finish_reason,
                index=primary_choice.get("index", 0),
                message=Message(
                    content=message_content,
                    role=message_role,
                    tool_calls=tool_calls or None,
                    function_call=function_call,
                ),
            )
        ],
        created=int(created or time.time()),
        model=response_payload.get("model", model),
        object=response_payload.get("object", "chat.completion"),
        system_fingerprint=system_fingerprint,
        usage=_build_usage(usage_payload),
    )


def build_streaming_chunk(response: ModelResponse) -> GenericStreamingChunk:
    """Build a minimal streaming chunk from a completed ModelResponse.

    This function creates a GenericStreamingChunk from a completed ModelResponse
    for compatibility with LiteLLM's streaming interface. It extracts the response
    content, finish reason, and metadata to create a single streaming chunk that
    represents the completed response.

    The chunk generation process:
    1. Extracts the primary choice from the response or creates a default
    2. Gets the message content and finish reason
    3. Creates provider-specific fields with response metadata
    4. Returns a streaming chunk marked as finished

    Parameters
    ----------
    response : ModelResponse
        Completed ModelResponse object to convert to streaming chunk format.

    Returns
    -------
    GenericStreamingChunk
        Streaming chunk representing the completed response with content,
        finish reason, and metadata.
    """
    choice = (
        response.choices[0]
        if response.choices
        else Choices(index=0, finish_reason="stop", message=Message(role="assistant", content=""))
    )
    content = choice.message.content if choice.message else ""
    finish_reason = choice.finish_reason or "stop"
    return GenericStreamingChunk(
        text=content or "",
        tool_use=None,
        is_finished=True,
        finish_reason=finish_reason,
        usage=None,
        index=0,
        provider_specific_fields={
            "id": response.id,
            "system_fingerprint": response.system_fingerprint,
        },
    )


def _extract_response_from_events(events: list[dict[str, Any]]) -> dict[str, Any]:
    """Extract final response payload from parsed SSE events using best-effort approach.

    Searches through events in reverse order for completion markers and response payloads.
    Used as fallback when typed model validation fails.

    Parameters
    ----------
    events : list[dict[str, Any]]
        Parsed SSE events containing potential response payloads.

    Returns
    -------
    dict[str, Any]
        Extracted response payload or empty dict when none found.
    """
    for event in reversed(events):
        if event.get("type") in {"response.done", "response.completed"}:
            response_payload = event.get("response") or event.get("data")
            if isinstance(response_payload, Mapping):
                return dict(response_payload)
        if "response" in event and isinstance(event["response"], Mapping):
            return dict(event["response"])

    if events:
        last = events[-1]
        if isinstance(last, Mapping):
            return dict(last)
    return {}


def _build_usage(usage: Mapping[str, Any] | None) -> Usage:
    """Build normalized usage statistics from various token counting schemes.

    Normalizes usage data from different API formats into LiteLLM's Usage object.
    Handles multiple token field names and calculates totals when not provided.

    Parameters
    ----------
    usage : Mapping[str, Any] | None
        Usage payload from the API response.

    Returns
    -------
    Usage
        Normalized usage statistics with prompt, completion, and total tokens.
    """
    usage_data = usage or {}
    prompt_tokens = usage_data.get("prompt_tokens", usage_data.get("input_tokens", 0))
    completion_tokens = usage_data.get("completion_tokens", usage_data.get("output_tokens", 0))
    total_tokens = usage_data.get("total_tokens") or (
        (prompt_tokens or 0) + (completion_tokens or 0)
    )
    return Usage(
        prompt_tokens=int(prompt_tokens or 0),
        completion_tokens=int(completion_tokens or 0),
        total_tokens=int(total_tokens or 0),
    )


def _coerce_output_fragment(fragment: Any) -> list[str]:
    """Extract text content from various output fragment formats.

    Handles different content formats, extracting text from strings, nested arrays,
    or converting other types to string representation. Recursively processes structures.

    Parameters
    ----------
    fragment : Any
        Output fragment to normalize.

    Returns
    -------
    list[str]
        Extracted text parts from the fragment.
    """
    if isinstance(fragment, Mapping):
        texts: list[str] = []
        text_value = fragment.get("text")
        if isinstance(text_value, str):
            texts.append(text_value)
        content = fragment.get("content")
        if isinstance(content, str):
            texts.append(content)
        elif isinstance(content, list):
            for part in content:
                texts.extend(_coerce_output_fragment(part))
        elif content is not None and not text_value:
            texts.append(str(content))
        return texts

    if isinstance(fragment, str):
        return [fragment]
    return [str(fragment)]


def _extract_text_from_output(output: Any) -> str:
    """Extract and concatenate text content from output structures.

    Processes output data in various formats and extracts all text content,
    concatenating into a single string with newlines between fragments.

    Parameters
    ----------
    output : Any
        Output payload from Codex response.

    Returns
    -------
    str
        Combined text representation.
    """
    fragments = output if isinstance(output, list) else [output]
    parts: list[str] = []
    for fragment in fragments:
        parts.extend(_coerce_output_fragment(fragment))
    return "\n".join(part for part in parts if part).strip()


def _coerce_choices_from_output(output: Any) -> list[dict[str, Any]]:
    """Extract completion choices from output items in various formats.

    Processes output items to extract completion choices in standard OpenAI format.
    Handles message and function_call types, converting to choice structure.

    Parameters
    ----------
    output : Any
        Output payload that may include message or function_call entries.

    Returns
    -------
    list[dict[str, Any]]
        Choices in OpenAI-compatible structure.
    """
    items = output if isinstance(output, list) else []
    for item in items:
        if isinstance(item, Mapping) and item.get("type") == "message":
            content_text = _extract_text_from_output(item.get("content", []))
            status = item.get("status")
            finish_reason = "stop" if status == "completed" else None
            return [
                {
                    "index": 0,
                    "finish_reason": finish_reason,
                    "message": {"role": item.get("role", "assistant"), "content": content_text},
                }
            ]
        if isinstance(item, Mapping) and item.get("type") == "function_call":
            arguments = item.get("arguments", "")
            if isinstance(arguments, (dict, list)):
                arguments = json.dumps(arguments)
            tool_calls = [
                {
                    "id": item.get("call_id", "tool_call_0"),
                    "type": item.get("type", "function"),
                    "function": {"name": item.get("name"), "arguments": arguments},
                }
            ]
            return [
                {
                    "index": 0,
                    "finish_reason": "tool_calls",
                    "message": {
                        "role": item.get("role", "assistant"),
                        "content": None,
                        "tool_calls": tool_calls,
                    },
                }
            ]
    fallback_text = _extract_text_from_output(items)
    return [
        {
            "index": 0,
            "finish_reason": None,
            "message": {"role": "assistant", "content": fallback_text},
        }
    ]


def _collect_tool_calls(
    message_payload: Mapping[str, Any], response_payload: Mapping[str, Any]
) -> list[dict[str, Any]]:
    """Collect tool calls from message payload and response output with fallback handling.

    Extracts tool calls from message payload first, then falls back to response output.
    Normalizes arguments to JSON string format and handles multiple tool call formats.

    Parameters
    ----------
    message_payload : Mapping[str, Any]
        Assistant message containing potential tool_calls field.
    response_payload : Mapping[str, Any]
        Full response payload containing output items when tool_calls absent.

    Returns
    -------
    list[dict[str, Any]]
        Normalized tool calls ready for LiteLLM.
    """
    tool_calls = _extract_tool_calls(message_payload)
    if tool_calls:
        return tool_calls

    output_items = response_payload.get("output", [])
    if not isinstance(output_items, list):
        return tool_calls

    for item in output_items:
        if not isinstance(item, Mapping) or item.get("type") != "function_call":
            continue
        arguments = item.get("arguments", "")
        if isinstance(arguments, (dict, list)):
            arguments = json.dumps(arguments)
        tool_calls.append(
            {
                "id": item.get("call_id") or item.get("id") or "tool_call_0",
                "type": item.get("type", "function"),
                "function": {"name": item.get("name"), "arguments": arguments},
            }
        )
    return tool_calls


def _extract_tool_calls(message_payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Extract and normalize tool calls from message payload.

    Processes tool_calls field and normalizes them into consistent format.
    Handles various tool call structures and argument types for LiteLLM compatibility.

    Parameters
    ----------
    message_payload : Mapping[str, Any]
        Assistant message with optional `tool_calls` field.

    Returns
    -------
    list[dict[str, Any]]
        Normalized tool call entries.
    """
    tool_calls_payload = message_payload.get("tool_calls") or []
    if not isinstance(tool_calls_payload, list):
        return []

    tool_calls: list[dict[str, Any]] = []
    for index, tool_call in enumerate(tool_calls_payload):
        if not isinstance(tool_call, Mapping):
            continue

        function_payload = tool_call.get("function", {})
        if not isinstance(function_payload, Mapping):
            function_payload = {}

        function_name = function_payload.get("name") or tool_call.get("name")
        arguments = function_payload.get("arguments", tool_call.get("arguments", ""))
        if isinstance(arguments, (dict, list)):
            arguments = json.dumps(arguments)

        tool_calls.append(
            {
                "id": tool_call.get("id") or tool_call.get("call_id") or f"tool_call_{index}",
                "type": tool_call.get("type", "function"),
                "function": {
                    "name": function_name,
                    "arguments": arguments,
                },
            }
        )

    return tool_calls


def _resolve_message_content(
    message_payload: Mapping[str, Any],
    response_payload: Mapping[str, Any],
    tool_calls: list[dict[str, Any]],
) -> tuple[str | None, str]:
    """Resolve message content and role with fallback handling.

    Determines final message content and role by checking multiple sources.
    Tool calls take precedence over content; falls back to response output when needed.

    Parameters
    ----------
    message_payload : Mapping[str, Any]
        Assistant message payload.
    response_payload : Mapping[str, Any]
        Full response payload containing potential output text.
    tool_calls : list[dict[str, Any]]
        Extracted tool calls influencing content selection.

    Returns
    -------
    tuple[str | None, str]
        Tuple of (content, role) for the assistant message.
    """
    message_content = message_payload.get("content")
    if tool_calls and (message_content is None or message_content == ""):
        message_content = None
    if not tool_calls and (message_content is None or message_content == ""):
        output_fallback = response_payload.get("output")
        if output_fallback is not None:
            message_content = _extract_text_from_output(output_fallback)
    message_role = message_payload.get("role", "assistant")
    return message_content, message_role


def _coerce_function_call(message_payload: Mapping[str, Any]) -> dict[str, Any] | None:
    """Extract and normalize function call from message payload.

    Processes function_call field and normalizes it for LiteLLM compatibility.
    Handles various function call formats and argument types.

    Parameters
    ----------
    message_payload : Mapping[str, Any]
        Assistant message payload that may include `function_call`.

    Returns
    -------
    dict[str, Any] | None
        Normalized function call payload or ``None`` when absent.
    """
    function_call = message_payload.get("function_call")
    if not isinstance(function_call, Mapping):
        return None

    function_call_args = function_call.get("arguments", "")
    if isinstance(function_call_args, (dict, list)):
        function_call_args = json.dumps(function_call_args)
    return {"name": function_call.get("name"), "arguments": function_call_args}


def _resolve_finish_reason(
    primary_choice: Mapping[str, Any], tool_calls: list[dict[str, Any]]
) -> str | None:
    """Resolve finish reason with tool call fallback logic.

    Determines appropriate finish reason by checking primary choice and applying
    fallback logic when tool calls are present. Ensures consistent reporting.

    Parameters
    ----------
    primary_choice : Mapping[str, Any]
        Primary completion choice from the response.
    tool_calls : list[dict[str, Any]]
        Tool calls found in the message or output.

    Returns
    -------
    str | None
        Finish reason string or ``None`` when not provided.
    """
    finish_reason = primary_choice.get("finish_reason")
    if tool_calls and not finish_reason:
        return "tool_calls"
    return finish_reason
