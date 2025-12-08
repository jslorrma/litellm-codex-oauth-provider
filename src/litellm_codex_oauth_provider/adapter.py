"""Pure adapters to reshape Codex responses into LiteLLM types."""

from __future__ import annotations

import json
import time
from collections.abc import Mapping
from typing import TYPE_CHECKING, Any

from litellm import Choices, Message, ModelResponse
from litellm.types.utils import GenericStreamingChunk, Usage

if TYPE_CHECKING:
    import httpx


def parse_response_body(response: httpx.Response) -> dict[str, Any]:
    """Return JSON payload from Codex response, handling buffered SSE."""
    content_type = (response.headers.get("content-type") or "").lower()
    body_text = response.text
    if "text/event-stream" in content_type or body_text.lstrip().startswith("event:"):
        parsed = convert_sse_to_json(body_text)
        if parsed:
            return parsed
        raise RuntimeError("Codex API returned stream without final response event")
    try:
        return response.json()
    except json.JSONDecodeError as exc:
        raise RuntimeError("Codex API returned invalid JSON") from exc


def convert_sse_to_json(payload: str) -> dict[str, Any]:
    """Convert buffered SSE text to final JSON payload."""
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
    """Transform OpenAI API response to LiteLLM format."""
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
        created=response_payload.get("created", int(time.time())),
        model=response_payload.get("model", model),
        object=response_payload.get("object", "chat.completion"),
        system_fingerprint=system_fingerprint,
        usage=_build_usage(usage_payload),
    )


def build_streaming_chunk(response: ModelResponse) -> GenericStreamingChunk:
    """Build a minimal streaming chunk from a completed response."""
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
    """Return the final response payload from parsed SSE events."""
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
    fragments = output if isinstance(output, list) else [output]
    parts: list[str] = []
    for fragment in fragments:
        parts.extend(_coerce_output_fragment(fragment))
    return "\n".join(part for part in parts if part).strip()


def _coerce_choices_from_output(output: Any) -> list[dict[str, Any]]:
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
    finish_reason = primary_choice.get("finish_reason")
    if tool_calls and not finish_reason:
        return "tool_calls"
    return finish_reason
