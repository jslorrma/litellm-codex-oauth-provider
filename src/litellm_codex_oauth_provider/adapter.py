r"""Pure adapters to reshape Codex responses into LiteLLM types.

This module provides pure functions for transforming OpenAI API responses from the Codex
backend into LiteLLM-compatible formats. It handles multiple response types including
Server-Sent Events (SSE), JSON responses, and typed OpenAI models.

The adapter system supports:
- Server-Sent Events (SSE) processing with buffered text handling
- Multiple response format detection and parsing
- OpenAI typed model validation with fallback mechanisms
- Tool call extraction from various response formats
- Usage statistics normalization across different token counting schemes
- Streaming chunk generation for compatibility

Response Processing Pipeline
----------------------------
1. **Format Detection**: Identify response type (SSE, JSON, or typed)
2. **Parsing**: Extract JSON payload using appropriate method
3. **Validation**: Validate using OpenAI typed models when possible
4. **Transformation**: Convert to LiteLLM ModelResponse format
5. **Tool Handling**: Extract and normalize tool calls
6. **Usage Building**: Normalize token usage statistics

Supported Response Formats
--------------------------
- **SSE (Server-Sent Events)**: Streamed responses with event: data format
- **JSON**: Direct JSON responses from the API
- **Typed Models**: OpenAI Response model validation
- **Legacy Formats**: Backward compatibility with older response structures

Tool Call Handling
------------------
The adapter handles multiple tool call formats:
- OpenAI format: `{"tool_calls": [{"function": {"name": "...", "arguments": "..."}}]}`
- Codex format: `{"output": [{"type": "function_call", "name": "...", "arguments": "..."}]}`
- Mixed formats: Combinations of the above with fallbacks

Examples
--------
Basic response transformation:

>>> from litellm_codex_oauth_provider.adapter import transform_response
>>> openai_response = {"response": {"choices": [{"message": {"content": "Hello"}}]}}
>>> model_response = transform_response(openai_response, "gpt-5.1-codex")
>>> print(model_response.choices[0].message.content)

SSE to JSON conversion:

>>> from litellm_codex_oauth_provider.adapter import convert_sse_to_json
>>> sse_text = 'data: {"response": {"choices": [...]}}\\ndata: [DONE]'
>>> json_response = convert_sse_to_json(sse_text)

Response body parsing:

>>> from litellm_codex_oauth_provider.adapter import parse_response_body
>>> import httpx
>>> response = httpx.get("https://api.example.com")
>>> data = parse_response_body(response)

Streaming chunk generation:

>>> from litellm_codex_oauth_provider.adapter import build_streaming_chunk
>>> chunk = build_streaming_chunk(model_response)

Notes
-----
- All functions are pure (no side effects) for predictable behavior
- SSE processing handles buffered text with proper event extraction
- Typed model validation provides strict schema checking
- Fallback mechanisms ensure robustness across API changes
- Tool call extraction supports both OpenAI and Codex formats
- Usage statistics normalize different token counting schemes

See Also
--------
- `ModelResponse`: LiteLLM response model
- `GenericStreamingChunk`: Streaming response chunk
- `Usage`: Token usage statistics
"""

from __future__ import annotations

import json
import logging
import time
from collections.abc import Mapping
from typing import TYPE_CHECKING, Any

from litellm import Choices, Message, ModelResponse
from litellm.types.utils import GenericStreamingChunk, Usage
from openai.types.responses import Response, ResponseStreamEvent

if TYPE_CHECKING:
    import httpx


logger = logging.getLogger(__name__)


def parse_response_body(response: httpx.Response) -> dict[str, Any]:
    """Return JSON payload from Codex response, handling buffered SSE.

    This function parses HTTP responses from the Codex API, handling both standard
    JSON responses and Server-Sent Events (SSE) streams. It automatically detects
    the response type and applies the appropriate parsing strategy.

    The parsing process:
    1. Checks Content-Type header for SSE detection
    2. For SSE: Converts buffered text to final JSON payload
    3. For JSON: Attempts typed model validation first, then raw JSON parsing
    4. Provides fallback mechanisms for robustness

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
    - SSE detection is based on Content-Type header and response text patterns
    - OpenAI typed model validation provides strict schema checking
    - Fallback to raw JSON parsing ensures robustness
    - SSE processing extracts the final response event from buffered text
    - Detailed logging available for debugging parsing issues

    See Also
    --------
    - `convert_sse_to_json`: Convert SSE text to JSON
    - `Response`: OpenAI typed response model
    """
    content_type = (response.headers.get("content-type") or "").lower()
    body_text = response.text
    if "text/event-stream" in content_type or body_text.lstrip().startswith("event:"):
        parsed = convert_sse_to_json(body_text)
        if parsed:
            return parsed
        raise RuntimeError("Codex API returned stream without final response event")
    try:
        # Use OpenAI's typed Response model for strict schema validation and parsing.
        # If this fails (e.g., due to schema mismatch or unexpected fields), fall back to raw JSON parsing below.
        return Response.model_validate_json(response.content).model_dump()
    except json.JSONDecodeError as exc:
        raise RuntimeError("Codex API returned invalid JSON") from exc
    except Exception as exc:
        logger.debug(
            "OpenAI typed response validation failed; falling back to raw JSON",
            extra={
                "status_code": response.status_code,
                "headers": dict(response.headers),
                "error": str(exc),
            },
        )
        try:
            # Fallback: parse raw JSON if typed model validation fails
            return response.json()
        except Exception as json_exc:
            raise RuntimeError("Codex API response could not be parsed as JSON") from json_exc


def convert_sse_to_json(payload: str) -> dict[str, Any]:
    r"""Convert buffered SSE text to final JSON payload.

    This function processes Server-Sent Events (SSE) text data and extracts the final
    JSON response payload. It handles the SSE format where events are separated by
    "data:" lines and may contain completion markers like "[DONE]".

    The conversion process:
    1. Splits payload into individual lines for processing
    2. Filters lines that don't start with "data:" prefix
    3. Extracts JSON data from data lines, skipping empty or completion markers
    4. Parses JSON events and validates they are Mapping types
    5. Attempts typed model validation first using _extract_validated_response_from_events
    6. Falls back to best-effort extraction using _extract_response_from_events
    7. Returns the final validated response payload

    Parameters
    ----------
    payload : str
        Buffered SSE text containing multiple data events, typically from
        streaming API responses.

    Returns
    -------
    dict[str, Any]
        Final JSON response payload extracted from SSE events.

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
    - Typed validation: Uses OpenAI Response models when available
    - Fallback extraction: Best-effort parsing when typed validation fails
    - Error handling: Skips invalid JSON events and continues processing
    - Event order: Processes events in order but extracts final response

    See Also
    --------
    - `_extract_validated_response_from_events`: Typed model validation
    - `_extract_response_from_events`: Best-effort extraction
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

    validated = _extract_validated_response_from_events(events)
    if validated:
        return validated

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
    """Extract the final response payload from parsed SSE events using best-effort approach.

    This function implements a fallback extraction strategy for SSE events when typed
    model validation fails or is not available. It searches through events in reverse
    order to find the final response, looking for specific completion markers and
    response payloads.

    The extraction strategy:
    1. Processes events in reverse order (newest first)
    2. Looks for completion events with specific type markers
    3. Extracts response or data payloads from completion events
    4. Falls back to any event containing a response field
    5. Returns the last valid event if no completion marker found
    6. Returns empty dict if no valid events are found

    Parameters
    ----------
    events : list[dict[str, Any]]
        List of parsed SSE events in dictionary format.

    Returns
    -------
    dict[str, Any]
        The extracted response payload, or empty dict if no valid response found.
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


def _extract_validated_response_from_events(events: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Validate SSE events using OpenAI typed models and return the first successful response.

    This function attempts to validate SSE events using OpenAI's typed models for strict
    schema validation. It processes events in reverse order and returns the first
    successfully validated response payload, providing detailed error logging for
    debugging validation failures.

    The validation process:
    1. Processes events in reverse order (newest first for efficiency)
    2. Attempts to validate each event as ResponseStreamEvent
    3. Extracts response payload from validated stream events
    4. Validates response payload using OpenAI Response model
    5. Returns first successfully validated response
    6. Logs validation errors for debugging when debug logging is enabled

    Parameters
    ----------
    events : list[dict[str, Any]]
        List of parsed SSE events to validate using typed models.

    Returns
    -------
    dict[str, Any] | None
        First successfully validated response payload, or None if no events validate.
    """
    validation_errors: list[str] = []
    validated_response: dict[str, Any] | None = None
    for event in reversed(events):
        try:
            typed_event = ResponseStreamEvent.model_validate(event)
        except Exception as exc:
            if logger.isEnabledFor(logging.DEBUG):
                validation_errors.append(f"event-parse: {exc}")
            continue
        response_payload = getattr(typed_event, "response", None)
        if response_payload is None:
            continue
        try:
            validated_response = Response.model_validate(response_payload).model_dump()
            break
        except Exception as exc:
            if logger.isEnabledFor(logging.DEBUG):
                validation_errors.append(f"response-validate: {exc}")
            continue

    if validation_errors and logger.isEnabledFor(logging.DEBUG):
        error_summary_limit = 5
        # Log a single summary line to avoid per-event noise.
        logger.debug(
            "Failed to validate response stream events; falling back to raw extraction",
            extra={
                "errors": validation_errors[:error_summary_limit],
                "errors_truncated": len(validation_errors) > error_summary_limit,
            },
        )
    return validated_response


def _build_usage(usage: Mapping[str, Any] | None) -> Usage:
    """Build normalized usage statistics from various token counting schemes.

    This function normalizes usage statistics from different API response formats
    into LiteLLM's standard Usage object. It handles multiple token field names
    and calculates total tokens when not explicitly provided.

    The normalization process:
    1. Handles None input by creating zero usage
    2. Extracts prompt tokens from multiple possible field names
    3. Extracts completion tokens from multiple possible field names
    4. Calculates total tokens if not explicitly provided
    5. Converts all values to integers and creates Usage object

    Parameters
    ----------
    usage : Mapping[str, Any] | None
        Usage data from API response, may contain various token field names
        like 'prompt_tokens', 'input_tokens', 'completion_tokens', 'output_tokens', 'total_tokens'.

    Returns
    -------
    Usage
        Normalized usage statistics with prompt_tokens, completion_tokens, and total_tokens.
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

    This function handles different content formats within output fragments,
    extracting text from strings, nested content arrays, or converting other
    types to string representation. It recursively processes nested structures.

    The extraction process:
    1. Handles Mapping objects by checking for text and content fields
    2. Extracts text from 'text' field if present
    3. Processes 'content' field (string, list, or other types)
    4. Recursively processes nested content arrays
    5. Converts non-text content to string representation
    6. Returns list of extracted text fragments

    Parameters
    ----------
    fragment : Any
        Content fragment that may be a string, mapping, list, or other type.

    Returns
    -------
    list[str]
        List of text fragments extracted from the content.
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

    This function processes output data that may be in various formats (list, dict, etc.)
    and extracts all text content, concatenating it into a single string with newlines
    between fragments. It handles nested structures and filters out empty content.

    The extraction process:
    1. Normalizes output to a list format for consistent processing
    2. Iterates through each fragment in the output
    3. Extracts text from each fragment using _coerce_output_fragment
    4. Concatenates all text fragments with newlines
    5. Filters out empty strings and strips whitespace

    Parameters
    ----------
    output : Any
        Output data that may be a list, dict, string, or other format containing text content.

    Returns
    -------
    str
        Concatenated text content from all fragments, with newlines between non-empty fragments.
    """
    fragments = output if isinstance(output, list) else [output]
    parts: list[str] = []
    for fragment in fragments:
        parts.extend(_coerce_output_fragment(fragment))
    return "\n".join(part for part in parts if part).strip()


def _coerce_choices_from_output(output: Any) -> list[dict[str, Any]]:
    """Extract completion choices from output items in various formats.

    This function processes output items to extract completion choices in the standard
    OpenAI format. It handles different item types including messages and function calls,
    converting them to the expected choice structure with proper content and finish reasons.

    The extraction process:
    1. Normalizes output to list format for consistent processing
    2. Iterates through items looking for message and function_call types
    3. For message items: extracts content and sets finish_reason based on status
    4. For function_call items: creates tool_calls and sets tool_calls finish_reason
    5. Returns first valid choice found, or creates fallback choice from text

    Parameters
    ----------
    output : Any
        Output data containing items that may include messages or function calls.

    Returns
    -------
    list[dict[str, Any]]
        List containing a single choice dict with message content and finish_reason.
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

    This function implements a comprehensive tool call extraction strategy that checks
    multiple locations in the response data. It first attempts to extract tool calls
    from the message payload, then falls back to checking the response output items
    for function call definitions.

    The collection process:
    1. First attempts extraction from message payload using _extract_tool_calls
    2. If no tool calls found in message, checks response output items
    3. Processes output items looking for function_call type items
    4. Extracts function call details including name, arguments, and call ID
    5. Normalizes arguments to JSON string format when needed
    6. Returns combined list of all found tool calls

    Parameters
    ----------
    message_payload : Mapping[str, Any]
        Message payload that may contain tool_calls field.
    response_payload : Mapping[str, Any]
        Response payload that may contain output items with function calls.

    Returns
    -------
    list[dict[str, Any]]
        List of normalized tool call dictionaries with id, type, function name, and arguments.

    Notes
    -----
    - Prioritizes message payload tool calls over output items
    - Handles multiple tool call formats and argument types
    - Generates fallback call IDs when not provided
    - Normalizes arguments to JSON string format for consistency
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

    This function processes the tool_calls field in message payloads and normalizes
    them into a consistent format. It handles various tool call structures and
    argument types, ensuring compatibility with LiteLLM's expected format.

    The extraction process:
    1. Retrieves tool_calls payload from message or returns empty list
    2. Validates that payload is a list type
    3. Iterates through each tool call in the payload
    4. Extracts function details from nested function payload or direct fields
    5. Normalizes arguments to JSON string format when needed
    6. Generates fallback IDs when not provided
    7. Returns list of normalized tool call dictionaries

    Parameters
    ----------
    message_payload : Mapping[str, Any]
        Message payload that may contain tool_calls field.

    Returns
    -------
    list[dict[str, Any]]
        List of normalized tool call dictionaries with id, type, function name, and arguments.

    Notes
    -----
    - Handles both OpenAI and Codex tool call formats
    - Normalizes arguments to JSON string format for consistency
    - Generates sequential IDs when call_id not provided
    - Validates payload structure and skips invalid entries
    - Supports nested function payload extraction
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

    This function determines the final message content and role by checking multiple
    sources and applying appropriate fallback logic. It handles cases where content
    may be in different locations or formats depending on the response structure.

    The resolution process:
    1. Retrieves initial content from message payload
    2. If tool calls exist and content is empty, sets content to None
    3. If no tool calls and content is empty, attempts fallback from response output
    4. Extracts text from output fallback using _extract_text_from_output
    5. Determines message role with assistant as default
    6. Returns tuple of resolved content and role

    Parameters
    ----------
    message_payload : Mapping[str, Any]
        Message payload containing content and role fields.
    response_payload : Mapping[str, Any]
        Response payload that may contain output fallback content.
    tool_calls : list[dict[str, Any]]
        List of tool calls that may affect content resolution logic.

    Returns
    -------
    tuple[str | None, str]
        Tuple containing resolved message content (may be None) and role string.

    Notes
    -----
    - Tool calls take precedence over content when both are present
    - Output fallback only used when no tool calls and content is empty
    - Role defaults to "assistant" when not specified
    - Content may be None when tool calls are present without text
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

    This function processes the function_call field in message payloads and normalizes
    it into a consistent format for compatibility with LiteLLM's expected structure.
    It handles various function call formats and argument types.

    The coercion process:
    1. Retrieves function_call field from message payload
    2. Validates that function_call is a Mapping type
    3. Extracts function name and arguments from the function_call
    4. Normalizes arguments to JSON string format when needed
    5. Returns normalized function call dictionary or None if invalid

    Parameters
    ----------
    message_payload : Mapping[str, Any]
        Message payload that may contain function_call field.

    Returns
    -------
    dict[str, Any] | None
        Normalized function call dictionary with name and arguments, or None if invalid.

    Notes
    -----
    - Returns None for non-Mapping function_call types
    - Normalizes arguments to JSON string format for consistency
    - Handles both dict and list argument types
    - Maintains backward compatibility with legacy function call formats
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

    This function determines the appropriate finish reason for a response by checking
    the primary choice's finish reason and applying fallback logic when tool calls
    are present. It ensures consistent finish reason reporting across different
    response formats.

    The resolution process:
    1. Retrieves finish_reason from primary choice
    2. If tool calls exist and no finish reason is set, returns "tool_calls"
    3. Otherwise returns the original finish reason (may be None)
    4. Ensures tool calls are properly reflected in finish reason

    Parameters
    ----------
    primary_choice : Mapping[str, Any]
        Primary choice object that may contain finish_reason field.
    tool_calls : list[dict[str, Any]]
        List of tool calls that may require tool_calls finish reason.

    Returns
    -------
    str | None
        Resolved finish reason string or None if not applicable.

    Notes
    -----
    - Tool calls take precedence when no explicit finish reason provided
    - Maintains original finish reason when tool calls are not present
    - Ensures consistent "tool_calls" finish reason for function calling
    - Supports various finish reason formats from different APIs
    """
    finish_reason = primary_choice.get("finish_reason")
    if tool_calls and not finish_reason:
        return "tool_calls"
    return finish_reason
