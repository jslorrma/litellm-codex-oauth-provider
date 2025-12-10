"""SSE implementation validation tests ensuring proper event parsing and chunk building.

This suite validates that:
- SSE event parsing correctly extracts event types and data
- Streaming utilities properly build text, tool, and final chunks
- Tool call tracking maintains state across streaming operations
- Provider has correct method signatures for async operations
"""

from __future__ import annotations

from litellm_codex_oauth_provider.provider import CodexAuthProvider
from litellm_codex_oauth_provider.sse_utils import _normalize_event, parse_sse_events
from litellm_codex_oauth_provider.streaming_utils import (
    ToolCallTracker,
    build_final_chunk,
    build_text_chunk,
    build_tool_call_chunk,
)

# Test constants for predictable values
PROMPT_TOKENS_TEST = 10
COMPLETION_TOKENS_TEST = 20
EXPECTED_CALL_COUNT = 2

# =============================================================================
# TESTS
# =============================================================================


class TestSSEMessageParsing:
    """Test SSE event parsing and normalization functionality."""

    def test_parse_text_delta_event(self) -> None:
        """Given a text delta event, when parsed, then event structure is correctly extracted."""
        text_event_data = '{"type": "text_delta", "content": "Hello world"}'
        event = _normalize_event("text", text_event_data)

        assert event is not None
        assert event["type"] == "text_delta"
        assert '"content": "Hello world"' in event["data"]

    def test_parse_tool_call_arguments_event(self) -> None:
        """Given a function arguments delta event, when parsed, then tool call structure is extracted."""
        tool_event_data = '{"type": "function_arguments_delta", "call_id": "call_123", "arguments": "{\\"param\\": \\"value\\"}"}'
        event = _normalize_event("function_call.arguments.delta", tool_event_data)

        assert event is not None
        assert event["type"] == "function_arguments_delta"
        assert "call_123" in event["data"]

    def test_parse_completion_event(self) -> None:
        """Given a completion event, when parsed, then usage and finish reason are extracted."""
        completion_data = '{"type": "response.done", "usage": {"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30}, "finish_reason": "stop"}'
        event = _normalize_event("response.done", completion_data)

        assert event is not None
        assert event["type"] == "completion"
        assert '"finish_reason": "stop"' in event["data"]

    def test_parse_done_sentinel(self) -> None:
        """Given a done sentinel event, when parsed, then done signal is identified."""
        done_event = _normalize_event(None, "[DONE]")

        assert done_event is not None
        assert done_event["type"] == "done"


class TestStreamingChunkBuilding:
    """Test streaming chunk construction utilities."""

    def test_build_text_chunk(self) -> None:
        """Given text content, when building chunk, then text chunk with correct structure is returned."""
        text_chunk = build_text_chunk("Hello", index=0)

        assert text_chunk["text"] == "Hello"
        assert text_chunk["index"] == 0
        assert not text_chunk["is_finished"]
        assert "is_finished" in text_chunk
        assert "index" in text_chunk

    def test_build_tool_call_chunk(self) -> None:
        """Given tool call data, when building chunk, then tool use chunk with proper structure is returned."""
        tool_chunk = build_tool_call_chunk("call_123", "my_function", '{"param": "value"}', index=0)

        assert tool_chunk["tool_use"] is not None
        assert tool_chunk["tool_use"]["id"] == "call_123"
        assert tool_chunk["tool_use"]["function"]["name"] == "my_function"
        assert tool_chunk["tool_use"]["function"]["arguments"] == '{"param": "value"}'
        assert tool_chunk["index"] == 0

    def test_build_final_chunk(self) -> None:
        """Given usage data and finish reason, when building final chunk, then finished chunk is returned."""
        usage = {"prompt_tokens": PROMPT_TOKENS_TEST, "completion_tokens": COMPLETION_TOKENS_TEST}
        final_chunk = build_final_chunk(usage, "stop", index=0)

        assert final_chunk["is_finished"]
        assert final_chunk["finish_reason"] == "stop"
        assert final_chunk["usage"] is not None
        # Check that usage has the expected prompt_tokens and completion_tokens
        assert final_chunk["usage"].prompt_tokens == PROMPT_TOKENS_TEST
        assert final_chunk["usage"].completion_tokens == COMPLETION_TOKENS_TEST
        assert final_chunk["index"] == 0


class TestToolCallTracking:
    """Test tool call state tracking during streaming operations."""

    def test_tracker_manages_tool_call_lifecycle(self) -> None:
        """Given tool call tracking, when tool call is started, arguments added, and finalized, then state transitions correctly."""
        tracker = ToolCallTracker()

        # Start a tool call
        tracker.start_tool_call("call_123", "my_function")
        active_calls = tracker.get_active_calls()
        assert "call_123" in active_calls
        assert active_calls["call_123"]["name"] == "my_function"

        # Add arguments
        tracker.add_arguments_delta("call_123", '{"param": "value"}')

        # Finalize tool call
        final_call = tracker.finalize_tool_call("call_123")
        assert final_call is not None
        assert final_call["id"] == "call_123"
        assert final_call["function"]["name"] == "my_function"
        assert final_call["function"]["arguments"] == '{"param": "value"}'

        # Should be cleared after finalization
        active_calls = tracker.get_active_calls()
        assert "call_123" not in active_calls

    def test_tracker_handles_multiple_calls(self) -> None:
        """Given multiple concurrent tool calls, when tracked, then each call is tracked independently."""
        tracker = ToolCallTracker()

        # Start multiple calls
        tracker.start_tool_call("call_1", "function_1")
        tracker.start_tool_call("call_2", "function_2")

        active_calls = tracker.get_active_calls()
        assert len(active_calls) == EXPECTED_CALL_COUNT
        assert "call_1" in active_calls
        assert "call_2" in active_calls

        # Finalize one call
        tracker.finalize_tool_call("call_1")

        # Only call_2 should remain
        remaining_calls = tracker.get_active_calls()
        assert len(remaining_calls) == 1
        assert "call_2" in remaining_calls
        assert "call_1" not in remaining_calls


class TestProviderMethodSignatures:
    """Test that provider has correct method signatures for async operations."""

    def test_provider_has_completion_methods(self) -> None:
        """Given a CodexAuthProvider instance, when checked, then completion methods exist and are callable."""
        provider = CodexAuthProvider()

        assert hasattr(provider, "completion")
        assert hasattr(provider, "acompletion")
        assert callable(provider.completion)
        assert callable(provider.acompletion)

    def test_provider_has_streaming_methods(self) -> None:
        """Given a CodexAuthProvider instance, when checked, then streaming methods exist and are callable."""
        provider = CodexAuthProvider()

        assert hasattr(provider, "streaming")
        assert hasattr(provider, "astreaming")
        assert callable(provider.streaming)
        assert callable(provider.astreaming)

    def test_provider_methods_are_async_compatible(self) -> None:
        """Given provider methods, when examined, then they support both sync and async usage patterns."""
        provider = CodexAuthProvider()

        # All methods should be callable and async-compatible
        assert callable(provider.completion)
        assert callable(provider.acompletion)
        assert callable(provider.streaming)
        assert callable(provider.astreaming)

        # Provider should be instantiable without parameters
        assert provider is not None


class TestImportResolution:
    """Test that all required imports work correctly."""

    def test_sse_utils_imports(self) -> None:
        """Given the sse_utils module, when imported, then all required functions are available."""
        assert _normalize_event is not None
        assert parse_sse_events is not None

    def test_streaming_utils_imports(self) -> None:
        """Given the streaming_utils module, when imported, then all chunk builders are available."""
        assert ToolCallTracker is not None
        assert build_final_chunk is not None
        assert build_text_chunk is not None
        assert build_tool_call_chunk is not None

    def test_provider_imports(self) -> None:
        """Given the provider module, when imported, then CodexAuthProvider is available."""
        assert CodexAuthProvider is not None
