#! /usr/bin/env python3
"""HTTpx Mock Implementation with Validation Callbacks

This module provides comprehensive testing infrastructure for the LiteLLM Codex provider
using httpx-level mocking with intelligent validation callbacks.
"""

from __future__ import annotations

import asyncio
import inspect
import json
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock

import httpx

from tests.integration.constants import (
    REASONING_DELAYS,
    VALID_MODELS,
    VALID_REASONING_VALUES,
)

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Callable


@dataclass
class MockHTTPError(Exception):
    """Mock HTTP error for validation."""

    status_code: int
    message: str
    headers: dict[str, str] | None = None


class MockSSEResponse:
    """Mock SSE response that simulates real httpx.Response for streaming."""

    def __init__(
        self,
        status_code: int = 200,
        headers: dict[str, str] | None = None,
        content_generator: callable | None = None,
    ) -> None:
        self.status_code = status_code
        self.headers = headers or {}
        self.content_generator = content_generator
        self.is_closed = False

    async def iter_lines(self) -> AsyncIterator[bytes]:
        """Simulate async line iteration for SSE events."""
        if self.content_generator:
            stream = self.content_generator()
            if inspect.isasyncgen(stream) or hasattr(stream, "__aiter__"):
                async for line in stream:
                    if not self.is_closed:
                        yield line
            elif hasattr(stream, "__iter__"):
                for line in stream:
                    if not self.is_closed:
                        yield line

        # End of stream marker
        yield b""

    async def aiter_lines(self) -> AsyncIterator[str]:
        """Async line iteration that yields strings like httpx.Response."""
        if self.content_generator:
            stream = self.content_generator()
            if inspect.isasyncgen(stream) or hasattr(stream, "__aiter__"):
                async for line in stream:
                    if not self.is_closed:
                        # Convert bytes to string if needed
                        if isinstance(line, bytes):
                            yield line.decode("utf-8")
                        else:
                            yield line
            elif hasattr(stream, "__iter__"):
                for line in stream:
                    if not self.is_closed:
                        # Convert bytes to string if needed
                        if isinstance(line, bytes):
                            yield line.decode("utf-8")
                        else:
                            yield line

        # End of stream marker
        yield ""

    async def __aenter__(self) -> MockSSEResponse:
        """Enter async context manager."""
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: BaseException | None,
    ) -> None:
        """Exit async context manager and close stream."""
        self.is_closed = True

    def raise_for_status(self) -> None:
        """Raise error if status indicates failure."""
        if self.status_code >= httpx.codes.BAD_REQUEST:
            raise httpx.HTTPStatusError(
                f"{self.status_code} {httpx.codes.get_reason_phrase(self.status_code)}",
                request=MagicMock(),
                response=self,
            )

    @property
    def text(self) -> str:
        """Return text representation of response."""
        return ""  # For non-streaming usage


class MockJSONResponse:
    """Mock JSON response for non-streaming requests."""

    def __init__(self, json_data: Any, status_code: int = 200) -> None:
        self.json_data = json_data
        self.status_code = status_code
        self.headers = {"content-type": "application/json"}
        self.is_closed = False

    def json(self) -> Any:
        """Return JSON data."""
        return self.json_data

    async def __aenter__(self) -> MockJSONResponse:
        """Enter async context manager."""
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: BaseException | None,
    ) -> None:
        """Exit async context manager and close response."""
        self.is_closed = True

    def raise_for_status(self) -> None:
        """Raise error if status indicates failure."""
        if self.status_code >= httpx.codes.BAD_REQUEST:
            raise httpx.HTTPStatusError(
                f"{self.status_code} {httpx.codes.get_reason_phrase(self.status_code)}",
                request=MagicMock(),
                response=self,
            )


class RequestValidator:
    """Validates Codex API requests with comprehensive validation rules."""

    def __init__(self, scenario: str = "default") -> None:
        self.scenario = scenario

    def validate_post_responses(self, request_data: dict) -> bool:
        """Validate POST /responses request format."""
        if self.scenario == "error_401":
            raise MockHTTPError(401, "Unauthorized")

        # Model validation
        model = request_data.get("model")
        if not self._validate_model(model):
            raise MockHTTPError(404, f"Model '{model}' not found")

        # Message validation
        messages = request_data.get("input", [])
        if not self._validate_messages(messages):
            raise MockHTTPError(400, "Invalid message format")

        # Instructions validation
        instructions = request_data.get("instructions")
        if not self._validate_instructions(instructions, model):
            raise MockHTTPError(400, "Invalid or missing instructions")

        # Reasoning validation
        reasoning_effort = request_data.get("reasoning_effort")
        if not self._validate_reasoning_effort(reasoning_effort):
            valid_values = VALID_REASONING_VALUES
            raise MockHTTPError(
                400,
                f"Invalid reasoning_effort: '{reasoning_effort}'. Must be one of: {valid_values}",
            )

        # Tool validation if present
        tools = request_data.get("tools")
        if tools and not self._validate_tools(tools):
            raise MockHTTPError(400, "Invalid tool format")

        # Stream parameter validation
        stream = request_data.get("stream", True)
        if not isinstance(stream, bool):
            raise MockHTTPError(400, "Stream parameter must be boolean")

        return True

    def _validate_model(self, model: str) -> bool:
        """Validate model format and availability."""
        if not model:
            return False

        # Check if it's a valid Codex model
        return model in VALID_MODELS

    def _validate_reasoning_effort(self, reasoning_effort: str | None) -> bool:
        """Validate reasoning_effort parameter."""
        if reasoning_effort is None:
            return True  # Optional parameter

        return reasoning_effort.lower() in VALID_REASONING_VALUES

    def _validate_instructions(self, instructions: str, _model: str) -> bool:
        """Validate Codex-specific instructions."""
        if not instructions:
            raise MockHTTPError(400, "Instructions required for Codex models")

        # Simplify validation: accept any non-empty instructions for tests
        return True

    def _validate_messages(self, messages: list) -> bool:
        """Validate message format."""
        if not isinstance(messages, list):
            return False

        for message in messages:
            if not isinstance(message, dict):
                return False

            # Check required fields
            if "role" not in message or "content" not in message:
                return False

            # Validate role
            valid_roles = ["system", "user", "assistant", "tool", "developer"]
            if message["role"] not in valid_roles:
                return False

        return True

    def _validate_tools(self, tools: list) -> bool:
        """Validate tool format."""
        if not isinstance(tools, list):
            return False

        for tool in tools:
            if not isinstance(tool, dict):
                return False

            # Accept both OpenAI-style {"function": {...}} and flattened definitions.
            if "function" in tool:
                function = tool["function"]
                if not isinstance(function, dict):
                    return False
                if "name" not in function or "description" not in function:
                    return False
            elif "name" not in tool or "description" not in tool:
                return False

        return True


class MockSSEGenerator:
    """Generates realistic SSE response streams."""

    def __init__(self, scenario: str = "default") -> None:
        self.scenario = scenario
        self.response_templates = self._load_response_templates()

    def _load_response_templates(self) -> dict[str, Any]:
        """Load response templates for different scenarios."""
        return {
            "basic_completion": {
                "content": "Hello, world! How can I help you today?",
                "reasoning_delay": 0.1,
            },
            "codex_native_streaming": {
                "reasoning": "Implementing simple greeting response...",
                "content": "Hello! Codex here to help you get started.",
            },
            "reasoning_low": {"content": "Sure, here's your answer.", "reasoning_delay": 0.05},
            "reasoning_high": {
                "content": "Let me think through this step by step...",
                "reasoning_delay": 0.15,
            },
            "tool_call_streaming": {
                "content_prefix": "I can help with that command.",
                "tool_calls": [
                    {
                        "id": "call_123",
                        "name": "bash_execute",
                        "arguments": '{"command": "ls -la", "timeout": 30}',
                    }
                ],
                "reasoning_delay": 0.05,
            },
            "mixed_response": {
                "content_prefix": "I'll execute a command for you.",
                "tool_calls": [
                    {
                        "id": "call_456",
                        "name": "python_execute",
                        "arguments": '{"code": "print(\\"Hello World\\")", "timeout": 10}',
                    }
                ],
                "reasoning_delay": 0.1,
            },
        }

    async def generate_text_response(self, request_data: dict) -> AsyncIterator[bytes]:
        """Generate text delta SSE events."""
        reasoning_effort = request_data.get("reasoning_effort", "medium")
        self._get_delay_for_reasoning(reasoning_effort)

        template = self.response_templates.get(self.scenario, {})
        content = template.get("content", "Hello, how can I assist you?")

        # Stream text word by word
        words = content.split()
        for i, word in enumerate(words):
            event_data = {
                "type": "text.delta",
                "content": word + (" " if i < len(words) - 1 else ""),
            }

            sse_event = f"event: text\ndata: {json.dumps(event_data)}\n\n"
            yield sse_event.encode("utf-8")

            # Realistic delay based on reasoning_effort
            await asyncio.sleep(0)  # Allow other tasks to run

        # Completion event
        yield self._generate_completion_event(request_data)

    async def generate_tool_call_response(self, request_data: dict) -> AsyncIterator[bytes]:
        """Generate tool call SSE events."""
        template = self.response_templates.get(self.scenario, {})
        tool_calls = template.get("tool_calls", [])
        content_prefix = template.get("content_prefix", "")

        if content_prefix:
            words = content_prefix.split()
            for i, word in enumerate(words):
                event_data = {
                    "type": "text.delta",
                    "content": word + (" " if i < len(words) - 1 else ""),
                }
                sse_event = f"event: text\ndata: {json.dumps(event_data)}\n\n"
                yield sse_event.encode("utf-8")

        for tool_call in tool_calls:
            # Stream arguments incrementally
            arguments = tool_call["arguments"]
            chunk_size = 10

            for i in range(0, len(arguments), chunk_size):
                chunk = arguments[i : i + chunk_size]

                event_data = {
                    "type": "function_call.arguments.delta",
                    "call_id": tool_call["id"],
                    "arguments": chunk,
                }

                sse_event = f"event: function_call_arguments\ndata: {json.dumps(event_data)}\n\n"
                yield sse_event.encode("utf-8")

            # Final tool call event
            final_event_data = {
                "type": "function_call.done",
                "call_id": tool_call["id"],
                "arguments": arguments,
            }

            final_event = f"event: function_call\ndata: {json.dumps(final_event_data)}\n\n"
            yield final_event.encode("utf-8")

        # Completion event
        yield self._generate_completion_event(request_data)

    def _generate_completion_event(self, _request_data: dict) -> bytes:
        """Generate completion event with usage."""
        usage = {"prompt_tokens": 20, "completion_tokens": 15, "total_tokens": 35}

        completion_data = {"type": "response.done", "usage": usage, "finish_reason": "stop"}

        event = f"event: response\ndata: {json.dumps(completion_data)}\n\n"
        return event.encode("utf-8")

    def _get_delay_for_reasoning(self, reasoning_effort: str) -> float:
        """Get appropriate delay based on reasoning_effort."""
        return REASONING_DELAYS.get(reasoning_effort.lower(), 0.1)

    def supports_streaming(self, _url: str, request_data: dict) -> bool:
        """Check if this request should use streaming."""
        return request_data.get("stream", True)

    def select_generator(self, request_data: dict) -> Callable[[dict], AsyncIterator[bytes]]:
        """Return the appropriate SSE generator based on scenario or presence of tools."""
        if self.scenario == "codex_native_streaming":
            return self.generate_codex_native_stream
        if self.scenario in {"tool_call_streaming", "mixed_response"} or request_data.get("tools"):
            return self.generate_tool_call_response
        return self.generate_text_response

    async def generate_codex_native_stream(self, _request_data: dict) -> AsyncIterator[bytes]:
        """Simulate the granular Codex SSE stream based on captured dump."""
        template = self.response_templates.get(self.scenario, {})
        reasoning = template.get("reasoning", "")
        content = template.get("content", "")

        # created event
        yield b"event: response.created\n"
        yield b'data: {"type":"response.created"}\n\n'

        # reasoning item start
        reasoning_item_id = "rs_1"
        yield f'event: response.output_item.added\ndata: {{"item":{{"id":"{reasoning_item_id}","type":"reasoning"}}}}\n\n'.encode()

        # reasoning part start
        yield f'event: response.reasoning_summary_part.added\ndata: {{"item_id":"{reasoning_item_id}"}}\n\n'.encode()

        # reasoning deltas
        for chunk in reasoning.split():
            delta = chunk + " "
            evt = {
                "type": "response.reasoning_summary_text.delta",
                "item_id": reasoning_item_id,
                "delta": delta,
            }
            yield f"event: response.reasoning_summary_text.delta\ndata: {json.dumps(evt)}\n\n".encode()

        # reasoning part done
        yield f'event: response.reasoning_summary_part.done\ndata: {{"item_id":"{reasoning_item_id}"}}\n\n'.encode()
        # reasoning item done
        yield f'event: response.output_item.done\ndata: {{"item_id":"{reasoning_item_id}"}}\n\n'.encode()

        # message item start
        msg_item_id = "msg_1"
        yield f'event: response.output_item.added\ndata: {{"item":{{"id":"{msg_item_id}","type":"message"}}}}\n\n'.encode()
        yield f'event: response.content_part.added\ndata: {{"item_id":"{msg_item_id}"}}\n\n'.encode()

        # content deltas
        for chunk in content.split():
            delta = chunk + " "
            evt = {
                "type": "response.output_text.delta",
                "item_id": msg_item_id,
                "delta": delta,
            }
            yield f"event: response.output_text.delta\ndata: {json.dumps(evt)}\n\n".encode()

        yield f'event: response.content_part.done\ndata: {{"item_id":"{msg_item_id}"}}\n\n'.encode()
        yield f'event: response.output_item.done\ndata: {{"item_id":"{msg_item_id}"}}\n\n'.encode()

        # completion with usage
        completion = {
            "type": "response.completed",
            "usage": {"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30},
            "finish_reason": "stop",
        }
        yield f"event: response.completed\ndata: {json.dumps(completion)}\n\n".encode()
        yield b"data: [DONE]\n\n"


class HTTpxMockManager:
    """Manages httpx mocking with validation callbacks."""

    def __init__(self) -> None:
        self.validator = RequestValidator()
        self.generator = MockSSEGenerator()
        self.original_methods = {}
        self.active_scenario = "default"
        self._is_active = False

    async def start_mock(self, scenario: str = "default") -> None:
        """Start httpx mocking with specified scenario."""
        self.active_scenario = scenario
        self.generator.scenario = scenario
        self.validator.scenario = scenario

        # Patch httpx.AsyncClient methods
        self._patch_post_methods()
        self._patch_stream_methods()

        self._is_active = True

    def _patch_post_methods(self) -> None:
        """Patch httpx post methods."""
        original_post = httpx.AsyncClient.post

        # Use closure to reference the mock manager instance
        mock_manager = self

        async def mock_post(
            _client: httpx.AsyncClient,
            url: str,
            *_args: Any,
            **kwargs: Any,
        ) -> MockJSONResponse | MockSSEResponse:
            # Parse request data
            request_data = kwargs.get("json", {})

            # Validate request
            try:
                mock_manager.validator.validate_post_responses(request_data)
            except MockHTTPError as e:
                return MockJSONResponse({"error": e.message}, status_code=e.status_code)

            # Generate mock response
            if mock_manager.generator.supports_streaming(url, request_data):
                return await mock_manager._generate_sse_response(request_data)  # noqa: SLF001
            return await mock_manager._generate_json_response(request_data)  # noqa: SLF001

        # Apply patches
        httpx.AsyncClient.post = mock_post
        self.original_methods["post"] = original_post

    def _patch_stream_methods(self) -> None:
        """Patch httpx stream methods."""
        original_stream = httpx.AsyncClient.stream

        # Use closure to reference the mock manager instance
        mock_manager = self

        def mock_stream(
            _client: httpx.AsyncClient,
            method: str,
            url: str,
            *_args: Any,
            **kwargs: Any,
        ) -> MockSSEResponse | MockJSONResponse:
            # For stream requests, we return a mock context manager
            if method.upper() == "POST" and "json" in kwargs:
                request_data = kwargs["json"]

                # Validate request
                try:
                    mock_manager.validator.validate_post_responses(request_data)
                except MockHTTPError as e:
                    return MockJSONResponse({"error": e.message}, status_code=e.status_code)

                if mock_manager.generator.supports_streaming(url, request_data):
                    stream_fn = mock_manager.generator.select_generator(request_data)
                    return MockSSEResponse(
                        status_code=200,
                        headers={"content-type": "text/event-stream"},
                        content_generator=lambda: stream_fn(request_data),
                    )

            # Fall back to original behavior
            return original_stream(_client, method, url, *_args, **kwargs)

        # Apply patches
        httpx.AsyncClient.stream = mock_stream
        self.original_methods["stream"] = original_stream

    async def _generate_sse_response(self, request_data: dict) -> MockSSEResponse:
        """Generate mock SSE response."""
        stream_fn = self.generator.select_generator(request_data)
        return MockSSEResponse(
            status_code=200,
            headers={"content-type": "text/event-stream"},
            content_generator=lambda: stream_fn(request_data),
        )

    async def _generate_json_response(self, request_data: dict) -> MockJSONResponse:
        """Generate mock JSON response."""
        mock_response_data = {
            "choices": [
                {
                    "finish_reason": "stop",
                    "index": 0,
                    "message": {"content": "Mock response content", "role": "assistant"},
                }
            ],
            "created": 1234567890,
            "id": "mock-response-id",
            "model": request_data.get("model", "gpt-5.1-codex"),
            "object": "chat.completion",
        }

        return MockJSONResponse(mock_response_data)

    async def stop_mock(self) -> None:
        """Stop httpx mocking and restore original methods."""
        if not self._is_active:
            return

        # Restore original methods
        for method_name, original_method in self.original_methods.items():
            if hasattr(httpx.AsyncClient, method_name):
                setattr(httpx.AsyncClient, method_name, original_method)

        self._is_active = False

    def set_scenario(self, scenario: str) -> None:
        """Change the active mock scenario."""
        self.active_scenario = scenario
        self.generator.scenario = scenario
        self.validator.scenario = scenario


# Convenience function for testing
@asynccontextmanager
async def mock_codex_api(scenario: str = "default") -> AsyncIterator[HTTpxMockManager]:
    """Context manager for easy use in tests."""
    mock_manager = HTTpxMockManager()

    try:
        await mock_manager.start_mock(scenario)
        yield mock_manager
    finally:
        await mock_manager.stop_mock()
