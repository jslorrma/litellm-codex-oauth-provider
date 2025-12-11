"""Streaming utilities for building LiteLLM-compatible streaming chunks.

This module provides functions for converting SSE events into GenericStreamingChunk
objects that are compatible with LiteLLM's streaming interface. It handles text
deltas, tool call arguments, and final chunks with proper formatting.

Key Functions:
- build_text_chunk: Create streaming chunk for text delta
- build_tool_call_chunk: Create streaming chunk for tool arguments
- build_final_chunk: Create final streaming chunk with usage
"""

from __future__ import annotations

from typing import TypedDict

from litellm.types.utils import GenericStreamingChunk, Usage


# Tool call chunk structures as defined in comments.md
class ChatCompletionToolCallFunctionChunk(TypedDict):
    """Function chunk in tool call."""

    name: str | None  # Function name, can be None for streaming deltas
    arguments: str  # JSON string of arguments


class ChatCompletionToolCallChunk(TypedDict):
    """Complete tool call chunk."""

    id: str | None  # Unique identifier for the tool call
    type: str  # Always "function" for function calls
    index: int  # Index in the response
    function: ChatCompletionToolCallFunctionChunk


def build_text_chunk(
    text_delta: str, index: int = 0, is_finished: bool = False, finish_reason: str | None = None
) -> GenericStreamingChunk:
    """Build streaming chunk for text delta.

    Parameters
    ----------
    text_delta : str
        Incremental text content from SSE event
    index : int, default 0
        Choice index in the response
    is_finished : bool, default False
        Whether this is the final chunk
    finish_reason : str | None
        Final reason for completion (stop, tool_calls, etc.)

    Returns
    -------
    GenericStreamingChunk
        Formatted streaming chunk for text content
    """
    return GenericStreamingChunk(
        text=text_delta,
        tool_use=None,
        is_finished=is_finished,
        finish_reason=finish_reason,
        index=index,
        usage=None,
    )


def build_reasoning_chunk(reasoning_delta: str, index: int = 0) -> GenericStreamingChunk:
    """Build streaming chunk for reasoning delta."""
    return GenericStreamingChunk(
        text="",
        tool_use=None,
        is_finished=False,
        finish_reason=None,
        index=index,
        usage=None,
        reasoning_content=reasoning_delta,
    )


def build_tool_call_chunk(
    call_id: str, name: str, arguments: str, is_final: bool = False, index: int = 0
) -> GenericStreamingChunk:
    """Build streaming chunk for tool call arguments.

    Parameters
    ----------
    call_id : str
        Unique identifier for the tool call
    name : str
        Name of the function being called
    arguments : str
        JSON string of function arguments (can be incremental)
    is_final : bool, default False
        Whether this is the final chunk for this tool call
    index : int, default 0
        Choice index in the response

    Returns
    -------
    GenericStreamingChunk
        Formatted streaming chunk for tool call
    """
    tool_call = ChatCompletionToolCallChunk(
        id=call_id,
        type="function",
        index=index,
        function=ChatCompletionToolCallFunctionChunk(name=name, arguments=arguments),
    )

    return GenericStreamingChunk(
        text="",
        tool_use=tool_call,
        is_finished=is_final,
        finish_reason="tool_calls" if is_final else None,
        index=index,
        usage=None,
    )


def build_tool_arguments_delta(arguments_delta: str, index: int = 0) -> GenericStreamingChunk:
    """Build streaming chunk for tool arguments delta.

    This is for incremental streaming of tool arguments when they arrive in chunks.

    Parameters
    ----------
    arguments_delta : str
        Incremental JSON arguments (partial string that gets concatenated)
    index : int, default 0
        Choice index in the response

    Returns
    -------
    GenericStreamingChunk
        Formatted streaming chunk for incremental tool arguments
    """
    tool_call = ChatCompletionToolCallChunk(
        id=None,  # ID can be None for incremental deltas
        type="function",
        index=index,
        function=ChatCompletionToolCallFunctionChunk(
            name=None,  # Name can be None for incremental deltas
            arguments=arguments_delta,
        ),
    )

    return GenericStreamingChunk(
        text="", tool_use=tool_call, is_finished=False, finish_reason=None, index=index, usage=None
    )


def build_final_chunk(
    usage: dict[str, int] | None, finish_reason: str, index: int = 0
) -> GenericStreamingChunk:
    """Build final streaming chunk with usage and finish reason.

    Parameters
    ----------
    usage : dict[str, int] | None
        Usage statistics (prompt_tokens, completion_tokens, total_tokens)
    finish_reason : str
        Reason for completion (stop, tool_calls, length, etc.)
    index : int, default 0
        Choice index in the response

    Returns
    -------
    GenericStreamingChunk
        Final streaming chunk with usage and completion status
    """
    usage_obj = None
    if usage:
        usage_obj = Usage(
            prompt_tokens=int(usage.get("prompt_tokens", 0)),
            completion_tokens=int(usage.get("completion_tokens", 0)),
            total_tokens=int(usage.get("total_tokens", 0)),
        )

    return GenericStreamingChunk(
        text="",
        tool_use=None,
        is_finished=True,
        finish_reason=finish_reason,
        index=index,
        usage=usage_obj,
    )


def build_completion_text_chunk(
    text: str, usage: dict[str, int] | None, finish_reason: str, index: int = 0
) -> GenericStreamingChunk:
    """Build streaming chunk for completed text response.

    This is used when converting non-streaming responses to streaming format.

    Parameters
    ----------
    text : str
        Final text content
    usage : dict[str, int] | None
        Usage statistics
    finish_reason : str
        Reason for completion
    index : int, default 0
        Choice index in the response

    Returns
    -------
    GenericStreamingChunk
        Formatted completion chunk
    """
    usage_obj = None
    if usage:
        usage_obj = Usage(
            prompt_tokens=int(usage.get("prompt_tokens", 0)),
            completion_tokens=int(usage.get("completion_tokens", 0)),
            total_tokens=int(usage.get("total_tokens", 0)),
        )

    return GenericStreamingChunk(
        text=text,
        tool_use=None,
        is_finished=True,
        finish_reason=finish_reason,
        index=index,
        usage=usage_obj,
    )


class ToolCallTracker:
    """Helper class to track tool call state during streaming.

    This class manages the state of tool calls as they stream incrementally,
    allowing proper accumulation of arguments and final tool call chunk creation.
    """

    def __init__(self) -> None:
        self._active_calls: dict[str, dict[str, str]] = {}

    def start_tool_call(self, call_id: str, name: str) -> None:
        """Start tracking a new tool call.

        Parameters
        ----------
        call_id : str
            Unique identifier for the tool call
        name : str
            Name of the function being called
        """
        self._active_calls[call_id] = {"name": name, "arguments": ""}

    def add_arguments_delta(self, call_id: str, arguments_delta: str) -> None:
        """Add incremental arguments to a tool call.

        Parameters
        ----------
        call_id : str
            Unique identifier for the tool call
        arguments_delta : str
            Incremental JSON arguments to append
        """
        if call_id in self._active_calls:
            self._active_calls[call_id]["arguments"] += arguments_delta

    def finalize_tool_call(self, call_id: str) -> ChatCompletionToolCallChunk | None:
        """Get final tool call chunk and remove from tracking.

        Parameters
        ----------
        call_id : str
            Unique identifier for the tool call

        Returns
        -------
        ChatCompletionToolCallChunk | None
            Complete tool call chunk or None if not found
        """
        if call_id not in self._active_calls:
            return None

        call_data = self._active_calls.pop(call_id)

        return ChatCompletionToolCallChunk(
            id=call_id,
            type="function",
            index=0,  # Simplified for now
            function=ChatCompletionToolCallFunctionChunk(
                name=call_data["name"], arguments=call_data["arguments"]
            ),
        )

    def get_active_calls(self) -> dict[str, dict[str, str]]:
        """Get currently active tool calls.

        Returns
        -------
        dict[str, dict[str, str]]
            Active tool calls with their current state
        """
        return self._active_calls.copy()

    def clear(self) -> None:
        """Clear all active tool calls."""
        self._active_calls.clear()
