"""Simplified LiteLLM provider for Codex OAuth.

This module provides a streamlined CustomLLM provider that bridges Codex CLI OAuth
authentication to OpenAI-compatible APIs with minimal complexity while maintaining
all essential functionality.

The simplified provider focuses on:
- Clear request/response flow
- Essential authentication handling
- Basic model normalization
- Simple payload preparation
- Reliable response transformation

See the legacy_complex.py module for the full-featured implementation.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from collections.abc import AsyncIterator, Mapping
from threading import Thread
from typing import TYPE_CHECKING, Any, TypeVar

from litellm import Choices, CustomLLM, Message, ModelResponse
from litellm.types.utils import Usage

from . import constants
from .auth import _decode_account_id, get_auth_context
from .exceptions import CodexAuthTokenExpiredError
from .http_client import CodexAPIClient
from .model_map import _strip_provider_prefix, get_model_family, normalize_model
from .prompts import DEFAULT_INSTRUCTIONS, build_tool_bridge_message, derive_instructions
from .reasoning import apply_reasoning_config
from .remote_resources import fetch_codex_instructions
from .sse_utils import extract_text_from_sse_event, extract_tool_call_from_sse_event
from .streaming_utils import (
    ToolCallTracker,
    build_final_chunk,
    build_reasoning_chunk,
    build_text_chunk,
    build_tool_call_chunk,
)

if TYPE_CHECKING:
    from litellm.types.utils import GenericStreamingChunk

logger = logging.getLogger(__name__)
T = TypeVar("T")
VALID_REASONING = {"none", "minimal", "low", "medium", "high", "xhigh"}
SUPPORTED_FAMILIES = {"codex", "codex-max", "codex-mini", "gpt-5.1"}


# Internal utility functions for pure logic operations
def _normalize_model(model: str) -> str:
    """Normalize model name for Codex API.

    Parameters
    ----------
    model : str
        Input model string (may include provider prefixes)

    Returns
    -------
    str
        Normalized model name for Codex API
    """
    return normalize_model(_strip_provider_prefix(model))


def _prepare_messages(
    messages: list[dict[str, Any]], tools: list[dict[str, Any]] | None = None
) -> list[dict[str, Any]]:
    """Prepare messages with optional tool bridge injection.

    Parameters
    ----------
    messages : list[dict[str, Any]]
        Chat messages provided by the caller
    tools : list[dict[str, Any]] | None
        Normalized tool definitions

    Returns
    -------
    list[dict[str, Any]]
        Input message list ready for inclusion in the `/responses` payload
    """
    input_messages = list(messages)
    if tools:
        input_messages = [build_tool_bridge_message(), *input_messages]
    return input_messages


def _build_payload(payload_parts: dict[str, Any]) -> dict[str, Any]:
    """Build the Codex responses API payload (shared by completion + streaming)."""
    payload = {
        "model": payload_parts["normalized_model"],
        "input": _prepare_messages(payload_parts["messages"], payload_parts["tools"]),
        "instructions": payload_parts["instructions"] or DEFAULT_INSTRUCTIONS,
        "include": [constants.REASONING_INCLUDE_TARGET],
        "store": False,
        "stream": True,  # Always use streaming for Codex
    }

    # Add tools if provided
    if payload_parts["tools"]:
        payload["tools"] = payload_parts["tools"]

    # Add reasoning config
    reasoning_config = apply_reasoning_config(
        original_model=_strip_provider_prefix(payload_parts["normalized_model"]),
        normalized_model=payload_parts["normalized_model"],
        reasoning_effort=payload_parts["reasoning_effort"],
        verbosity=payload_parts["verbosity"],
    )
    payload.update(reasoning_config)

    # Add basic passthrough options
    passthrough = {
        "metadata": payload_parts["optional_params"].get("metadata"),
        "user": payload_parts["optional_params"].get("user"),
    }
    payload.update({k: v for k, v in passthrough.items() if v is not None})

    return payload


def _prepare_common_payload(
    model: str,
    messages: list[dict[str, Any]],
    **kwargs: Any,
) -> tuple[dict[str, Any], str]:
    """Normalize inputs, derive instructions/tools, and return payload + normalized model."""
    normalized_model = _normalize_model(model)
    _validate_model_supported(normalized_model)

    validated_reasoning = _coerce_reasoning_effort(kwargs.get("reasoning_effort"))
    optional_params = kwargs.get("optional_params", {}) or {}
    tools = kwargs.get("tools") or optional_params.get("tools")
    normalized_tools = _normalize_tools(tools) if tools else None

    instructions_text = fetch_codex_instructions(normalized_model)
    instructions, prepared_messages = derive_instructions(
        messages,
        normalized_model=normalized_model,
        instructions_text=instructions_text,
    )

    payload = _build_payload(
        {
            "normalized_model": normalized_model,
            "instructions": instructions,
            "messages": prepared_messages,
            "tools": normalized_tools,
            "reasoning_effort": validated_reasoning,
            "verbosity": kwargs.get("verbosity"),
            "optional_params": optional_params,
        }
    )
    return payload, normalized_model


def _run_sync(coro: asyncio.Future | asyncio.Awaitable[T]) -> T:
    """Run a coroutine in a sync context, even if a loop is already running.

    The function checks if there's an active event loop. If not, it uses asyncio.run().
    If there is an active loop, it runs the coroutine in a separate thread to avoid
    conflicts.

    Parameters
    ----------
    coro : asyncio.Future | asyncio.Awaitable[T]
        Coroutine to run

    Returns
    -------
    T
        Result of the coroutine
    """
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)

    result: dict[str, Any] = {}
    exc: dict[str, BaseException] = {}

    def _runner() -> None:
        try:
            result["value"] = asyncio.run(coro)
        except BaseException as err:  # pragma: no cover - passthrough
            exc["err"] = err

    thread = Thread(target=_runner, daemon=True)
    thread.start()
    thread.join()

    if exc:
        raise exc["err"]
    return result["value"]


def _validate_model_supported(normalized_model: str) -> None:
    """Ensure the requested model maps to a supported family."""
    family = get_model_family(normalized_model)
    if family not in SUPPORTED_FAMILIES:
        raise ValueError(f"Model '{normalized_model}' not found")


def _coerce_reasoning_effort(reasoning_effort: Any | None) -> str | None:
    """Validate and normalize reasoning_effort input."""
    if reasoning_effort is None:
        return None

    value = None
    if isinstance(reasoning_effort, str):
        value = reasoning_effort
    elif isinstance(reasoning_effort, Mapping):
        inner = reasoning_effort.get("effort")
        if isinstance(inner, str):
            value = inner
    else:
        raise ValueError(
            "Invalid reasoning_effort. Must be one of: "
            f"{sorted(VALID_REASONING)} or a mapping with an 'effort' key."
        )

    if value is None:
        return None

    normalized = value.lower()
    if normalized not in VALID_REASONING:
        raise ValueError(
            f"Invalid reasoning_effort: '{value}'. Must be one of: {sorted(VALID_REASONING)}"
        )
    return normalized


def _normalize_tools(tools: list[dict[str, Any]] | None) -> list[dict[str, Any]] | None:
    """Normalize tool definitions to OpenAI-compliant schema.

    Simplified version that handles the basic case without excessive validation.

    Parameters
    ----------
    tools : list[dict[str, Any]] | None
        Raw tool definitions supplied to LiteLLM

    Returns
    -------
    list[dict[str, Any]] | None
        Normalized tool list or None when no tools are provided

    Raises
    ------
    ValueError
        If tool definitions are not provided as a list or required names are missing
    """
    if tools is None:
        return None

    if not isinstance(tools, list):
        raise ValueError("tools must be a list of tool definitions.")

    normalized = []
    for tool in tools:
        if not isinstance(tool, Mapping):
            normalized.append(tool)
            continue

        tool_dict = dict(tool)
        function_payload = tool_dict.pop("function", {})

        if isinstance(function_payload, Mapping) and function_payload:
            name = function_payload.get("name")
            if not name:
                raise ValueError("Each tool must include function.name")

            tool_dict.setdefault("name", name)
            tool_dict.setdefault("description", function_payload.get("description"))
            tool_dict.setdefault("parameters", function_payload.get("parameters", {}))
            tool_dict.setdefault("strict", function_payload.get("strict"))
            tool_dict.setdefault("type", "function")
        elif not tool_dict.get("name"):
            raise ValueError("Each tool must include name")
        else:
            tool_dict.setdefault("type", "function")

        normalized.append(tool_dict)

    return normalized


class CodexAuthProvider(CustomLLM):
    """Simplified CustomLLM provider for Codex OAuth authentication.

    This class provides a streamlined implementation that focuses on core functionality
    while maintaining full compatibility with LiteLLM. It handles the essential request/
    response lifecycle with reduced complexity.

    Key Features:
    - Automatic token management and refresh
    - Model normalization and instruction injection
    - Basic request/response transformation
    - SSE handling for streaming responses
    - Both sync and async operation support

    Examples
    --------
    Basic usage:

    >>> from litellm_codex_oauth_provider import CodexAuthProvider
    >>> provider = CodexAuthProvider()
    >>> response = provider.completion(
    ...     model="codex/gpt-5.1-codex", messages=[{"role": "user", "content": "Hello"}]
    ... )

    Async usage:

    >>> async def main():
    ...     provider = CodexAuthProvider()
    ...     response = await provider.acompletion(
    ...         model="codex/gpt-5.1-codex", messages=[{"role": "user", "content": "Hello"}]
    ...     )
    ...     return response

    Notes
    -----
    - Requires Codex CLI authentication via 'codex login'
    - Automatically handles token refresh and caching
    - Supports all GPT-5.1 Codex model variants
    - SSE streaming responses are properly handled
    - Thread-safe for concurrent usage
    """

    def __init__(self) -> None:
        """Initialize the CodexAuthProvider with simplified configuration."""
        super().__init__()

        # Enable debug logging if requested
        if os.getenv("CODEX_DEBUG", "").lower() in {"1", "true", "yes", "on", "debug"}:
            logging.basicConfig(level=logging.DEBUG)
            logger.debug("CODEX_DEBUG enabled; debug logging active.")

        # Cache for token management
        self._cached_token: str | None = None
        self._token_expiry: float | None = None
        self._account_id: str | None = None

        # Resolve base URL
        self.base_url = constants.CODEX_API_BASE_URL.rstrip("/") + "/codex"

        # Initialize HTTP client
        self._http_client = CodexAPIClient(
            token_provider=self.get_bearer_token,
            account_id_provider=self._resolve_account_id,
            base_url=self.base_url,
        )

    def get_bearer_token(self) -> str:
        """Get a valid bearer token, refreshing if necessary."""
        # Check if we have a valid cached token
        if (
            self._cached_token
            and self._token_expiry
            and time.time() < self._token_expiry - constants.TOKEN_CACHE_BUFFER_SECONDS
        ):
            return self._cached_token

        try:
            # Get fresh auth context
            context = get_auth_context()
            self._cached_token = context.access_token
            self._account_id = context.account_id
            self._token_expiry = time.time() + constants.TOKEN_DEFAULT_EXPIRY_SECONDS
            return context.access_token
        except CodexAuthTokenExpiredError:
            # Token expired - let it bubble up for now
            raise

    def _resolve_account_id(self) -> str | None:
        """Get cached account ID or extract from token."""
        if self._account_id:
            return self._account_id
        if self._cached_token:
            return _decode_account_id(self._cached_token)
        return None

    def completion(
        self,
        model: str,
        messages: list[dict[str, Any]],
        **kwargs: Any,
    ) -> ModelResponse:
        """Sync wrapper that delegates to async completion."""
        return _run_sync(self.acompletion(model, messages, **kwargs))

    async def acompletion(
        self,
        model: str,
        messages: list[dict[str, Any]],
        **kwargs: Any,
    ) -> ModelResponse:
        """Complete a chat completion request using Codex authentication with SSE accumulation."""
        payload, normalized_model = _prepare_common_payload(model, messages, **kwargs)

        # Process SSE events and build response
        accumulated_text, tool_calls, usage, finish_reason = await self._process_sse_events(
            self._http_client.stream_responses_sse(payload)
        )

        return self._build_model_response(
            accumulated_text, tool_calls, usage, finish_reason, normalized_model
        )

    def streaming(
        self,
        model: str,
        messages: list[dict[str, Any]],
        **kwargs: Any,
    ) -> AsyncIterator[GenericStreamingChunk]:
        """Sync wrapper that delegates to async streaming."""

        async def _collect() -> list[GenericStreamingChunk]:
            return [chunk async for chunk in self.astreaming(model, messages, **kwargs)]

        return iter(_run_sync(_collect()))

    async def astreaming(
        self,
        model: str,
        messages: list[dict[str, Any]],
        **kwargs: Any,
    ) -> AsyncIterator[GenericStreamingChunk]:
        """True streaming method that yields SSE events as streaming chunks."""
        payload, _normalized_model = _prepare_common_payload(model, messages, **kwargs)
        tool_tracker = ToolCallTracker()

        try:
            async for event in self._http_client.stream_responses_sse(payload):
                chunk = self._process_sse_streaming_event(event, tool_tracker)
                if chunk:
                    yield chunk
        except Exception as exc:
            logger.error(f"Error during SSE streaming: {exc}")
            raise RuntimeError(f"Failed to stream Codex response: {exc}") from exc

    def _process_sse_streaming_event(
        self, event: dict[str, Any], tool_tracker: ToolCallTracker
    ) -> GenericStreamingChunk | None:
        """Process individual SSE event for streaming.

        Parameters
        ----------
        event : dict[str, Any]
            SSE event to process
        tool_tracker : ToolCallTracker
            Tool call state tracker

        Returns
        -------
        GenericStreamingChunk | None
            Streaming chunk or None if no chunk to yield
        """
        event_type = event.get("type")
        handlers: dict[str, Any] = {
            "text_delta": self._build_text_chunk_from_event,
            "reasoning_delta": self._build_reasoning_chunk_from_event,
            "function_arguments_delta": lambda evt: self._build_tool_chunk_from_event(
                evt, tool_tracker
            ),
            "completion": self._build_completion_chunk_from_event,
        }

        handler = handlers.get(event_type)
        if not handler:
            return None

        return handler(event)

    def _build_text_chunk_from_event(self, event: dict[str, Any]) -> GenericStreamingChunk | None:
        text = extract_text_from_sse_event(event)
        if not text:
            return None
        return build_text_chunk(text)

    def _build_reasoning_chunk_from_event(
        self, event: dict[str, Any]
    ) -> GenericStreamingChunk | None:
        reasoning_delta = event.get("delta") or extract_text_from_sse_event(event)
        if not reasoning_delta:
            return None
        return build_reasoning_chunk(reasoning_delta)

    def _build_tool_chunk_from_event(
        self, event: dict[str, Any], tool_tracker: ToolCallTracker
    ) -> GenericStreamingChunk | None:
        tool_data = extract_tool_call_from_sse_event(event)
        if not tool_data:
            return None

        call_id = tool_data.get("call_id") or "unknown"
        arguments = tool_data.get("arguments", "")
        name = tool_data.get("name")

        if call_id not in tool_tracker.get_active_calls():
            tool_tracker.start_tool_call(call_id, name or "unknown")

        tool_tracker.add_arguments_delta(call_id, arguments)

        tracked_name = tool_tracker.get_active_calls().get(call_id, {}).get("name", "unknown")
        return build_tool_call_chunk(call_id, name or tracked_name, arguments)

    def _build_completion_chunk_from_event(self, event: dict[str, Any]) -> GenericStreamingChunk:
        usage = event.get("usage") or {}
        finish_reason = event.get("finish_reason") or "stop"

        data = event.get("data")
        if isinstance(data, str):
            try:
                parsed_data = json.loads(data)
                usage = parsed_data.get("usage", usage)
                finish_reason = parsed_data.get("finish_reason", finish_reason)
            except json.JSONDecodeError:
                pass
        elif isinstance(data, dict):
            usage = data.get("usage", usage)
            finish_reason = data.get("finish_reason", finish_reason)

        return build_final_chunk(usage, finish_reason)

    def _extract_completion_metadata(
        self, event: dict[str, Any], usage: dict[str, int], finish_reason: str
    ) -> tuple[dict[str, int], str]:
        usage_value = event.get("usage") or usage
        finish_value = event.get("finish_reason") or finish_reason

        data = event.get("data")
        if isinstance(data, str):
            try:
                parsed_data = json.loads(data)
                usage_value = parsed_data.get("usage", usage_value)
                finish_value = parsed_data.get("finish_reason", finish_value)
            except json.JSONDecodeError:
                pass
        elif isinstance(data, dict):
            usage_value = data.get("usage", usage_value)
            finish_value = data.get("finish_reason", finish_value)

        return usage_value, finish_value

    async def _process_sse_events(
        self, event_stream: AsyncIterator[dict[str, Any]]
    ) -> tuple[str, list[dict], dict[str, int], str]:
        """Process SSE events and accumulate content.

        Parameters
        ----------
        event_stream : AsyncIterator[dict[str, Any]]
            SSE event stream from the API

        Returns
        -------
        tuple[str, list[dict], dict[str, int], str]
            Accumulated text, tool calls, usage data, and finish reason
        """
        accumulated_text = ""
        tool_calls = []
        usage = {}
        finish_reason = "stop"

        try:
            async for event in event_stream:
                event_type = event.get("type")

                if event_type == "text_delta":
                    text = extract_text_from_sse_event(event)
                    if text:
                        accumulated_text += text
                elif event_type == "function_arguments_delta":
                    tool_data = extract_tool_call_from_sse_event(event)
                    if tool_data:
                        tool_calls.append(tool_data)
                elif event_type == "completion":
                    usage, finish_reason = self._extract_completion_metadata(
                        event, usage, finish_reason
                    )
                elif event_type == "done":
                    break
        except Exception as exc:
            logger.error(f"Error during SSE processing: {exc}")
            raise RuntimeError(f"Failed to process Codex response: {exc}") from exc

        return accumulated_text, tool_calls, usage, finish_reason

    def _build_model_response(
        self,
        text: str,
        tool_calls: list[dict],
        usage: dict[str, int],
        finish_reason: str,
        model: str,
    ) -> ModelResponse:
        """Build ModelResponse from accumulated SSE data.

        Parameters
        ----------
        text : str
            Accumulated text content
        tool_calls : list[dict]
            List of tool calls
        usage : dict[str, int]
            Usage statistics
        finish_reason : str
            Reason for completion
        model : str
            Model identifier

        Returns
        -------
        ModelResponse
            LiteLLM-compatible response object
        """

        def _coalesce_tool_calls(raw_calls: list[dict]) -> list[dict]:
            aggregated: dict[str, dict[str, Any]] = {}
            for call in raw_calls:
                call_id = call.get("call_id") or call.get("id") or "unknown"
                entry = aggregated.setdefault(
                    call_id,
                    {
                        "id": call_id,
                        "type": "function",
                        "function": {"name": call.get("name") or "unknown", "arguments": ""},
                    },
                )
                arguments = call.get("arguments") or ""
                entry["function"]["arguments"] += arguments
                if call.get("name"):
                    entry["function"]["name"] = call["name"]
            return list(aggregated.values())

        message = Message(
            content=text,
            role="assistant",
            tool_calls=_coalesce_tool_calls(tool_calls) if tool_calls else None,
        )

        usage_obj = None
        if usage:
            usage_obj = Usage(
                prompt_tokens=int(usage.get("prompt_tokens", 0)),
                completion_tokens=int(usage.get("completion_tokens", 0)),
                total_tokens=int(usage.get("total_tokens", 0)),
            )

        return ModelResponse(
            id=f"cmpl-{int(time.time())}",
            choices=[
                Choices(
                    finish_reason=finish_reason,
                    index=0,
                    message=message,
                )
            ],
            created=int(time.time()),
            model=model,
            object="chat.completion",
            usage=usage_obj,
        )

    # Global instance for LiteLLM compatibility


codex_auth_provider = CodexAuthProvider()
