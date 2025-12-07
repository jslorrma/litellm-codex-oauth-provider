"""Codex OAuth Authentication Provider for LiteLLM.

This module implements a custom LiteLLM provider that uses Codex CLI's OAuth
authentication to access ChatGPT Plus models through OpenAI API.
"""

from __future__ import annotations

import json
import os
import time
from collections.abc import Mapping
from typing import Any

import httpx
from litellm import Choices, CustomLLM, Message, ModelResponse
from litellm.types.utils import GenericStreamingChunk, Usage
from litellm.utils import CustomStreamWrapper

from . import constants
from .auth import _decode_account_id, _refresh_token, get_auth_context
from .exceptions import CodexAuthTokenExpiredError
from .model_map import normalize_model, strip_provider_prefix
from .prompts import DEFAULT_INSTRUCTIONS, build_tool_bridge_message, derive_instructions
from .reasoning import apply_reasoning_config


class CodexAuthProvider(CustomLLM):
    """Custom LiteLLM provider that uses Codex CLI's OAuth authentication."""

    def __init__(self) -> None:
        """Initialize the CodexAuthProvider."""
        super().__init__()
        self.base_url = constants.CODEX_API_BASE_URL
        self._cached_token: str | None = None
        self._token_expiry: float | None = None
        self._account_id: str | None = None
        self._codex_mode_enabled = self._resolve_codex_mode()

    @property
    def cached_token(self) -> str | None:
        """Return the cached bearer token, if present."""
        return self._cached_token

    @property
    def token_expiry(self) -> float | None:
        """Return the cached token expiry timestamp, if present."""
        return self._token_expiry

    @property
    def account_id(self) -> str | None:
        """Return the cached ChatGPT account ID, if present."""
        return self._account_id

    def _resolve_codex_mode(self) -> bool:
        """Resolve CODEX_MODE feature flag."""
        env_value = os.getenv(constants.CODEX_MODE_ENV)
        if env_value is None:
            return constants.DEFAULT_CODEX_MODE
        return env_value.strip().lower() not in {"0", "false", "off"}

    def get_bearer_token(self) -> str:
        """Get bearer token with caching and refresh handling."""
        if (
            self._cached_token
            and self._token_expiry
            and time.time() < self._token_expiry - constants.TOKEN_CACHE_BUFFER_SECONDS
        ):
            return self._cached_token

        try:
            context = get_auth_context()
        except CodexAuthTokenExpiredError as err:
            try:
                refreshed = _refresh_token()
                context = get_auth_context()
                if refreshed and not context.access_token:
                    context = context.__class__(
                        access_token=refreshed, account_id=_decode_account_id(refreshed)
                    )
            except Exception:
                raise err from None

        self._cached_token = context.access_token
        self._account_id = context.account_id
        self._token_expiry = time.time() + constants.TOKEN_DEFAULT_EXPIRY_SECONDS
        return context.access_token

    def _rewrite_url(self, api_base: str | None) -> str:
        base = (api_base or self.base_url).rstrip("/")
        if base.endswith(constants.CODEX_RESPONSES_ENDPOINT):
            return base
        if base.endswith(constants.OPENAI_RESPONSES_ENDPOINT):
            base = base[: -len(constants.OPENAI_RESPONSES_ENDPOINT)]
        return f"{base}{constants.CODEX_RESPONSES_ENDPOINT}"

    def _build_headers(self, bearer_token: str, *, prompt_cache_key: str | None) -> dict[str, str]:
        account_id = self._account_id or _decode_account_id(bearer_token)
        headers = {
            "Authorization": f"Bearer {bearer_token}",
            "Content-Type": "application/json",
            "accept": "text/event-stream",
            constants.CHATGPT_ACCOUNT_HEADER: account_id,
            constants.OPENAI_BETA_HEADER: constants.OPENAI_BETA_VALUE,
            constants.OPENAI_ORIGINATOR_HEADER: constants.OPENAI_ORIGINATOR_VALUE,
        }

        if prompt_cache_key:
            headers[constants.SESSION_ID_HEADER] = prompt_cache_key
            headers[constants.CONVERSATION_ID_HEADER] = prompt_cache_key

        return headers

    def _build_payload(
        self,
        *,
        model: str,
        instructions: str,
        messages: list[dict[str, Any]],
        prompt_cache_key: str | None,
        reasoning_config: dict[str, Any],
        **kwargs: Any,
    ) -> dict[str, Any]:
        optional_params = kwargs.pop("optional_params", {})
        normalized_tools = self._normalize_tools(
            kwargs.pop("tools", None) or optional_params.pop("tools", None)
        )

        payload: dict[str, Any] = {
            "model": model,
            "input": self._prepare_input(messages=messages, tools=normalized_tools),
            "instructions": instructions or DEFAULT_INSTRUCTIONS,
            "include": [constants.REASONING_INCLUDE_TARGET],
            "store": False,
            "stream": True,
            **reasoning_config,
            **optional_params,  # deprecated fallback
        }

        if normalized_tools:
            payload["tools"] = normalized_tools

        payload.update(self._filter_payload_options(kwargs))

        if prompt_cache_key:
            payload["prompt_cache_key"] = prompt_cache_key

        return payload

    def _prepare_input(
        self, *, messages: list[dict[str, Any]], tools: list[dict[str, Any]] | None
    ) -> list[dict[str, Any]]:
        """Return Codex-ready input, optionally prepending the bridge prompt when tools are used."""
        input_messages = list(messages)
        if self._codex_mode_enabled and tools:
            input_messages = [build_tool_bridge_message(), *input_messages]
        return input_messages

    @staticmethod
    def _filter_payload_options(options: Mapping[str, Any]) -> dict[str, Any]:
        passthrough_keys = {
            "frequency_penalty",
            "logprobs",
            "max_output_tokens",
            "max_tokens",
            "metadata",
            "n",
            "parallel_tool_calls",
            "presence_penalty",
            "response_format",
            "seed",
            "stop",
            "temperature",
            "tool_choice",
            "top_logprobs",
            "top_p",
            "user",
        }
        passthrough = {
            key: value
            for key, value in options.items()
            if key in passthrough_keys and value is not None
        }

        if "tools" in passthrough:
            passthrough["tools"] = CodexAuthProvider._normalize_tools(passthrough["tools"])

        max_tokens = passthrough.pop("max_tokens", None)
        if max_tokens is not None and "max_output_tokens" not in passthrough:
            passthrough["max_output_tokens"] = max_tokens

        return passthrough

    @staticmethod
    def _normalize_tools(tools: Any) -> list[dict[str, Any]] | None:
        if tools is None:
            return None
        if not isinstance(tools, list):
            raise ValueError("tools must be a list of tool definitions.")

        normalized: list[dict[str, Any]] = []
        for tool in tools:
            if not isinstance(tool, Mapping):
                normalized.append(tool)
                continue

            tool_dict = dict(tool)
            tool_type = tool_dict.pop("type", None) or "function"
            function_payload = tool_dict.pop("function", {})
            if isinstance(function_payload, Mapping) and function_payload:
                name = function_payload.get("name")
                if not name:
                    raise ValueError(
                        "Each tool must include function.name per OpenAI tools schema."
                    )
                tool_dict.setdefault("name", name)
                tool_dict.setdefault("description", function_payload.get("description"))
                tool_dict.setdefault("parameters", function_payload.get("parameters", {}))
            elif not tool_dict.get("name"):
                raise ValueError("Each tool must include name per OpenAI tools schema.")

            tool_dict.setdefault("type", tool_type)
            normalized.append(tool_dict)
        return normalized

    @staticmethod
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

            # Support both OpenAI function-call shape and Codex top-level shape
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

    def completion(
        self,
        model: str,
        messages: list[dict[str, Any]],
        api_base: str | None = None,
        custom_llm_provider: str | None = None,
        **kwargs: Any,
    ) -> ModelResponse:
        """Completion method - required by LiteLLM CustomLLM interface."""
        _ = custom_llm_provider  # parameter reserved by LiteLLM interface

        kwargs = dict(kwargs)
        prompt_cache_key = kwargs.pop("prompt_cache_key", None)
        bearer_token = self.get_bearer_token()

        normalized_model = normalize_model(strip_provider_prefix(model))
        instructions, input_messages = derive_instructions(
            messages,
            codex_mode=self._codex_mode_enabled,
            normalized_model=normalized_model,
        )
        reasoning_config = apply_reasoning_config(
            original_model=strip_provider_prefix(model),
            normalized_model=normalized_model,
            reasoning_effort=kwargs.get("reasoning_effort"),
            verbosity=kwargs.get("verbosity"),
        )

        payload = self._build_payload(
            model=normalized_model,
            instructions=instructions,
            messages=input_messages,
            prompt_cache_key=prompt_cache_key,
            reasoning_config=reasoning_config,
            **kwargs,
        )
        headers = self._build_headers(bearer_token, prompt_cache_key=prompt_cache_key)

        response = self._post_request(self._rewrite_url(api_base), payload, headers)
        data = self._parse_response_body(response)
        return self._transform_response(data, normalized_model)

    async def acompletion(
        self, model: str, messages: list[dict[str, Any]], api_base: str | None = None, **kwargs: Any
    ) -> ModelResponse:
        """Async completion for LiteLLM usage."""
        kwargs = dict(kwargs)
        prompt_cache_key = kwargs.pop("prompt_cache_key", None)
        bearer_token = self.get_bearer_token()

        normalized_model = normalize_model(strip_provider_prefix(model))
        instructions, input_messages = derive_instructions(
            messages,
            codex_mode=self._codex_mode_enabled,
            normalized_model=normalized_model,
        )
        reasoning_config = apply_reasoning_config(
            original_model=strip_provider_prefix(model),
            normalized_model=normalized_model,
            reasoning_effort=kwargs.get("reasoning_effort"),
            verbosity=kwargs.get("verbosity"),
        )

        payload = self._build_payload(
            model=normalized_model,
            instructions=instructions,
            messages=input_messages,
            prompt_cache_key=prompt_cache_key,
            reasoning_config=reasoning_config,
            **kwargs,
        )
        headers = self._build_headers(bearer_token, prompt_cache_key=prompt_cache_key)

        response = await self._post_request_async(self._rewrite_url(api_base), payload, headers)
        data = self._parse_response_body(response)
        return self._transform_response(data, normalized_model)

    def streaming(
        self,
        model: str,
        messages: list[dict[str, Any]],
        api_base: str | None = None,
        custom_llm_provider: str | None = None,
        **kwargs: Any,
    ) -> CustomStreamWrapper:
        """Simulate streaming by emitting a single generic streaming chunk."""
        completion_response = self.completion(
            model=model,
            messages=messages,
            api_base=api_base,
            custom_llm_provider=custom_llm_provider,
            **kwargs,
        )
        logging_obj = kwargs.get("logging_obj")
        chunk = self._build_streaming_chunk(completion_response)
        stream = (chunk for _ in [0])
        return CustomStreamWrapper(
            stream,
            model,
            logging_obj=logging_obj,
            custom_llm_provider=custom_llm_provider or "codex-oauth",
        )

    async def astreaming(
        self,
        model: str,
        messages: list[dict[str, Any]],
        api_base: str | None = None,
        custom_llm_provider: str | None = None,
        **kwargs: Any,
    ) -> CustomStreamWrapper:
        """Simulate async streaming by emitting a single generic streaming chunk."""
        completion_response = await self.acompletion(
            model=model,
            messages=messages,
            api_base=api_base,
            custom_llm_provider=custom_llm_provider,
            **kwargs,
        )
        logging_obj = kwargs.get("logging_obj")
        chunk = self._build_streaming_chunk(completion_response)

        async def async_stream() -> Any:
            yield chunk

        return CustomStreamWrapper(
            async_stream(),
            model,
            logging_obj=logging_obj,
            custom_llm_provider=custom_llm_provider or "codex-oauth",
        )

    def _post_request(
        self, url: str, payload: dict[str, Any], headers: dict[str, str]
    ) -> httpx.Response:
        try:
            with httpx.Client(timeout=60.0) as client:
                response = client.post(url, json=payload, headers=headers)
                response.raise_for_status()
                return response
        except httpx.HTTPStatusError as exc:
            raise RuntimeError(self._format_http_error(exc.response)) from exc
        except Exception as exc:  # pragma: no cover - network/transport errors
            raise RuntimeError(f"Codex API error: {exc}") from exc

    async def _post_request_async(
        self, url: str, payload: dict[str, Any], headers: dict[str, str]
    ) -> httpx.Response:
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(url, json=payload, headers=headers)
                response.raise_for_status()
                return response
        except httpx.HTTPStatusError as exc:
            raise RuntimeError(self._format_http_error(exc.response)) from exc
        except Exception as exc:  # pragma: no cover - network/transport errors
            raise RuntimeError(f"Codex API error: {exc}") from exc

    def _format_http_error(self, response: httpx.Response) -> str:
        detail = ""
        try:
            detail_json = response.json()
            detail = detail_json.get("error", {}).get("message") or detail_json.get("detail", "")
        except Exception:
            detail = response.content.decode(errors="ignore").strip()

        limit_headers = {
            header: value
            for header, value in response.headers.items()
            if header.lower().startswith("x-ratelimit")
        }
        rate_info = (
            f" | rate-limit hints: {', '.join(f'{k}={v}' for k, v in limit_headers.items())}"
            if limit_headers
            else ""
        )
        retry_after = response.headers.get("retry-after")
        retry_hint = f" | retry-after: {retry_after}s" if retry_after else ""
        return f"Codex API error {response.status_code}: {detail}{rate_info}{retry_hint}"

    def _parse_response_body(self, response: httpx.Response) -> dict[str, Any]:
        content_type = (response.headers.get("content-type") or "").lower()
        body_text = response.text
        if "text/event-stream" in content_type or body_text.lstrip().startswith("event:"):
            parsed = self._convert_sse_to_json(body_text)
            if parsed:
                return parsed
            raise RuntimeError("Codex API returned stream without final response event")
        try:
            return response.json()
        except json.JSONDecodeError as exc:
            raise RuntimeError("Codex API returned invalid JSON") from exc

    @staticmethod
    def _convert_sse_to_json(payload: str) -> dict[str, Any]:
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

        return CodexAuthProvider._extract_response_from_events(events)

    @staticmethod
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

    @staticmethod
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

    @staticmethod
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
                    texts.extend(CodexAuthProvider._coerce_output_fragment(part))
            elif content is not None and not text_value:
                texts.append(str(content))
            return texts

        if isinstance(fragment, str):
            return [fragment]
        return [str(fragment)]

    @staticmethod
    def _extract_text_from_output(output: Any) -> str:
        fragments = output if isinstance(output, list) else [output]
        parts: list[str] = []
        for fragment in fragments:
            parts.extend(CodexAuthProvider._coerce_output_fragment(fragment))
        return "\n".join(part for part in parts if part).strip()

    @staticmethod
    def _coerce_choices_from_output(output: Any) -> list[dict[str, Any]]:
        items = output if isinstance(output, list) else []
        for item in items:
            if isinstance(item, Mapping) and item.get("type") == "message":
                content_text = CodexAuthProvider._extract_text_from_output(item.get("content", []))
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
        # Fallback: join all output fragments
        fallback_text = CodexAuthProvider._extract_text_from_output(items)
        return [
            {
                "index": 0,
                "finish_reason": None,
                "message": {"role": "assistant", "content": fallback_text},
            }
        ]

    @staticmethod
    def _build_streaming_chunk(response: ModelResponse) -> GenericStreamingChunk:
        choice = (
            response.choices[0]
            if response.choices
            else Choices(
                index=0, finish_reason="stop", message=Message(role="assistant", content="")
            )
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

    def _transform_response(self, openai_response: dict[str, Any], model: str) -> ModelResponse:
        """Transform OpenAI API response to LiteLLM format."""
        response_payload = openai_response.get("response", openai_response)
        usage_payload = response_payload.get("usage") or openai_response.get("usage")
        choices = response_payload.get("choices")

        if not choices and "output" in response_payload:
            choices = self._coerce_choices_from_output(response_payload.get("output"))

        if not choices:
            raise RuntimeError("Codex API response is missing choices output")

        primary_choice = choices[0]
        message_payload = primary_choice.get("message") or {}
        tool_calls = self._collect_tool_calls(message_payload, response_payload)
        message_content, message_role = self._resolve_message_content(
            message_payload, response_payload, tool_calls
        )
        function_call = self._coerce_function_call(message_payload)
        system_fingerprint = response_payload.get("system_fingerprint") or openai_response.get(
            "system_fingerprint"
        )
        finish_reason = self._resolve_finish_reason(primary_choice, tool_calls)

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
            usage=self._build_usage(usage_payload),
        )

    def _collect_tool_calls(
        self, message_payload: Mapping[str, Any], response_payload: Mapping[str, Any]
    ) -> list[dict[str, Any]]:
        tool_calls = self._extract_tool_calls(message_payload)
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

    def _resolve_message_content(
        self,
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
                message_content = self._extract_text_from_output(output_fallback)
        message_role = message_payload.get("role", "assistant")
        return message_content, message_role

    def _coerce_function_call(self, message_payload: Mapping[str, Any]) -> dict[str, Any] | None:
        function_call = message_payload.get("function_call")
        if not isinstance(function_call, Mapping):
            return None

        function_call_args = function_call.get("arguments", "")
        if isinstance(function_call_args, (dict, list)):
            function_call_args = json.dumps(function_call_args)
        return {"name": function_call.get("name"), "arguments": function_call_args}

    @staticmethod
    def _resolve_finish_reason(
        primary_choice: Mapping[str, Any], tool_calls: list[dict[str, Any]]
    ) -> str | None:
        finish_reason = primary_choice.get("finish_reason")
        if tool_calls and not finish_reason:
            return "tool_calls"
        return finish_reason


# Instantiate the provider for convenience in LiteLLM mappings
codex_auth_provider = CodexAuthProvider()


class _StreamingLoggingStub:
    """Minimal logging stub to satisfy CustomStreamWrapper expectations."""

    def __init__(self) -> None:
        self.model_call_details: dict[str, Any] = {"litellm_params": {}}
        self.completion_start_time: Any = None

    def _update_completion_start_time(self, completion_start_time: Any) -> None:
        self.completion_start_time = completion_start_time

    def failure_handler(self, *_args: Any, **_kwargs: Any) -> None:
        return None

    def success_handler(self, *_args: Any, **_kwargs: Any) -> None:
        return None
