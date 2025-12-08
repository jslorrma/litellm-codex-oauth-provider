r"""System prompt handling and Codex instruction derivation.

This module handles the conversion of OpenAI message formats to Codex input format,
including system prompt processing, tool call normalization, and instruction derivation.

The prompt system supports:
- OpenAI to Codex message format conversion
- System prompt filtering and instruction extraction
- Tool call normalization and bridge prompt generation
- Legacy toolchain prompt detection and removal
- Function call output conversion to Codex schema

Message Processing Pipeline
---------------------------
1. **Role-based Processing**: Handle system, user, assistant, and tool messages
2. **Content Extraction**: Convert various content formats to text
3. **Tool Normalization**: Convert OpenAI tool calls to Codex format
4. **System Prompt Handling**: Extract and combine system instructions
5. **Bridge Prompt Addition**: Add tool bridge for function calling

Supported Message Types
-----------------------
- **System Messages**: Converted to Codex instructions
- **User Messages**: Direct conversion to Codex messages
- **Assistant Messages**: Preserved with content and tool calls
- **Tool Messages**: Converted to function_call_output format
- **Function Calls**: Normalized to Codex function_call schema

Tool Call Handling
------------------
The module handles multiple tool call formats:
- OpenAI format: `{"tool_calls": [{"function": {"name": "...", "arguments": "..."}}]}`
- Legacy format: `{"function_call": {"name": "...", "arguments": "..."}}`
- Function output: `{"function_call_output": "..."}`

Examples
--------
Message conversion:

>>> from litellm_codex_oauth_provider.prompts import _to_codex_input
>>> openai_message = {"role": "user", "content": "Hello"}
>>> codex_input = _to_codex_input(openai_message)
>>> print(codex_input)
{'type': 'message', 'content': 'Hello', 'role': 'user'}

Tool call conversion:

>>> tool_message = {"role": "tool", "tool_call_id": "call_123", "content": "Tool result"}
>>> codex_input = _to_codex_input(tool_message)
>>> print(codex_input)
{'type': 'function_call_output', 'output': {'tool_call_id': 'call_123', 'content': 'Tool result'}, 'role': 'assistant'}

Instruction derivation:

>>> from litellm_codex_oauth_provider.prompts import derive_instructions
>>> messages = [
...     {"role": "system", "content": "You are a helpful assistant."},
...     {"role": "user", "content": "Hello"},
... ]
>>> instructions, input_messages = derive_instructions(messages, normalized_model="gpt-5.1-codex")

Tool bridge message:

>>> from litellm_codex_oauth_provider.prompts import build_tool_bridge_message
>>> bridge = build_tool_bridge_message()
>>> print(bridge["content"][0]["text"][:50])
'# Codex Tool Bridge\\n\\nYou are an open-source AI coding assistant...'

Notes
-----
- System prompts are filtered for legacy toolchain markers
- Tool bridge prompts are added when tools are present
- Function calls are normalized to Codex schema
- Content is coerced to text format for consistency
- The module provides both individual conversion and batch derivation functions

See Also
--------
- `provider`: Main provider using these prompt functions
- `remote_resources`: Instruction fetching and caching
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from typing import Any, Final

from . import constants
from .remote_resources import fetch_codex_instructions

DEFAULT_INSTRUCTIONS: Final[str] = constants.DEFAULT_INSTRUCTIONS
LEGACY_TOOLCHAIN_MARKERS: Final[tuple[str, ...]] = (
    "toolchain system prompt",
    "toolchain::system",
    "legacy toolchain",
)
TOOL_BRIDGE_PROMPT: Final[str] = """# Codex Tool Bridge

You are an open-source AI coding assistant with tool support, running behind a developer CLI. \
When tools are provided, prefer invoking them via standard OpenAI tool calls, using the provided \
tool schema exactly. Do not fabricate results—issue tool calls whenever they are needed to satisfy \
the request."""


def _coerce_text(content: Any) -> str:
    """Convert OpenAI content payloads to plain text for inspection."""
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, dict):
        return _coerce_text(content.get("text") or content.get("content"))
    if isinstance(content, Iterable):
        parts = [_coerce_text(part) for part in content]
        return "\n".join(part for part in parts if part)
    return str(content)


def _is_toolchain_system_prompt(content: str) -> bool:
    """Identify legacy toolchain system prompts that should be filtered in Codex mode."""
    lowered = content.lower()
    return any(marker in lowered for marker in LEGACY_TOOLCHAIN_MARKERS)


def _strip_message_metadata(message: dict[str, Any]) -> dict[str, Any]:
    """Remove identifiers that are not part of the Codex schema."""
    return {key: value for key, value in message.items() if key not in {"id", "item_reference"}}


def _drop_stray_function_output(message: dict[str, Any]) -> dict[str, Any]:
    """Remove orphaned function_call_output payloads."""
    if (
        message.get("role") == "assistant"
        and "function_call_output" in message
        and "function_call" not in message
    ):
        cleaned = dict(message)
        cleaned.pop("function_call_output", None)
        return cleaned
    return message


def _clean_message_payload(message: dict[str, Any]) -> dict[str, Any]:
    """Normalize message payload by removing Codex-incompatible metadata."""
    stripped = _strip_message_metadata(message)
    return _drop_stray_function_output(stripped)


def _extract_tool_call(message: dict[str, Any]) -> dict[str, Any] | None:
    """Extract the first tool call from a message."""
    tool_calls = message.get("tool_calls")
    if not tool_calls:
        return None

    tool_call = tool_calls[0]
    if isinstance(tool_call, dict):
        arguments = tool_call.get("arguments", "")
        if isinstance(arguments, (dict, list)):
            arguments = json.dumps(arguments)
        return {
            "name": tool_call.get("name"),
            "arguments": arguments,
        }
    return None


def _normalize_function_output(message: dict[str, Any]) -> dict[str, Any] | None:
    """Convert tool role messages to Codex function_call_output schema."""
    if message.get("role") != "tool":
        return None
    tool_call_id = message.get("tool_call_id")
    output = message.get("content")
    if tool_call_id is not None:
        output = {"tool_call_id": tool_call_id, "content": output}
    return {
        "type": "function_call_output",
        "output": output,
        "role": message.get("role", "assistant"),
    }


def _normalize_function_call(message: dict[str, Any]) -> dict[str, Any] | None:
    """Normalize function call payloads into Codex schema."""
    tool_call = _extract_tool_call(message)
    if tool_call:
        return {
            "type": "function_call",
            "function_call": tool_call,
            "role": message.get("role", "assistant"),
        }
    if "function_call_output" in message:
        return {
            "type": "function_call_output",
            "output": message["function_call_output"],
            "role": message.get("role", "assistant"),
        }
    if "function_call" in message:
        return {
            "type": "function_call",
            "function_call": message["function_call"],
            "role": message.get("role", "assistant"),
        }
    return None


def _to_codex_input(message: dict[str, Any]) -> dict[str, Any]:
    """Convert a message to Codex input format.

    Parameters
    ----------
    message : dict
        Message payload.

    Returns
    -------
    dict
        Codex input schema.

    Examples
    --------
    >>> _to_codex_input({"role": "user", "content": "Hello"})
    {'type': 'message', 'content': 'Hello', 'role': 'user'}
    """
    function_output = _normalize_function_output(message)
    if function_output:
        return function_output

    normalized_function_call = _normalize_function_call(message)
    if normalized_function_call:
        return normalized_function_call

    return {
        "type": "message",
        "content": message.get("content"),
        "role": message.get("role", "user"),
    }


def derive_instructions(
    messages: list[dict[str, Any]],
    *,
    normalized_model: str,
    instructions_text: str | None = None,
) -> tuple[str, list[dict[str, Any]]]:
    """Extract instructions and convert messages into Codex `input` format.

    Parameters
    ----------
    messages : list of dict
        Chat messages to adapt to the Codex schema.
    normalized_model : str
        Normalized model identifier (reserved for future gating).
    instructions_text : str, optional
        Pre-fetched Codex instructions to prepend.

    Returns
    -------
    tuple[str, list[dict[str, Any]]]
        Combined instruction string and Codex-ready message payloads.
    """
    _ = normalized_model  # reserved for future gating logic
    system_parts: list[str] = []
    input_payload: list[dict[str, Any]] = []

    for message in messages:
        if message.get("role") == "system":
            content = _coerce_text(message.get("content"))
            if not content:
                continue
            if _is_toolchain_system_prompt(content):
                continue
            system_parts.append(content)
            continue

        cleaned = _clean_message_payload(message)
        input_payload.append(_to_codex_input(cleaned))

    base_instructions = instructions_text or DEFAULT_INSTRUCTIONS
    instructions_parts: list[str] = [base_instructions, *system_parts]
    instructions = "\n\n".join(part for part in instructions_parts if part) or DEFAULT_INSTRUCTIONS
    return instructions, input_payload


def build_tool_bridge_message() -> dict[str, Any]:
    """Return the Codex/OpenCode bridge developer message for tool-enabled requests."""
    return {
        "type": "message",
        "role": "developer",
        "content": [{"type": "input_text", "text": TOOL_BRIDGE_PROMPT}],
    }


get_codex_instructions = fetch_codex_instructions
