"""Codex OAuth Authentication Provider for LiteLLM.

This module implements a custom LiteLLM provider that uses Codex CLI's OAuth
authentication to access ChatGPT Plus models through OpenAI API.
"""

from __future__ import annotations

import os
import time
from collections.abc import Mapping
from typing import Any

import httpx
from litellm import CustomLLM, ModelResponse
from litellm.utils import CustomStreamWrapper

from . import constants
from .adapter import build_streaming_chunk, parse_response_body, transform_response
from .auth import _decode_account_id, _refresh_token, get_auth_context
from .exceptions import CodexAuthTokenExpiredError
from .model_map import normalize_model, strip_provider_prefix
from .prompts import DEFAULT_INSTRUCTIONS, build_tool_bridge_message, derive_instructions
from .reasoning import apply_reasoning_config
from .remote_resources import fetch_codex_instructions


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
        instructions_text = (
            fetch_codex_instructions(normalized_model) if self._codex_mode_enabled else None
        )
        instructions, input_messages = derive_instructions(
            messages,
            codex_mode=self._codex_mode_enabled,
            normalized_model=normalized_model,
            instructions_text=instructions_text,
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
        data = parse_response_body(response)
        return transform_response(data, normalized_model)

    async def acompletion(
        self, model: str, messages: list[dict[str, Any]], api_base: str | None = None, **kwargs: Any
    ) -> ModelResponse:
        """Async completion for LiteLLM usage."""
        kwargs = dict(kwargs)
        prompt_cache_key = kwargs.pop("prompt_cache_key", None)
        bearer_token = self.get_bearer_token()

        normalized_model = normalize_model(strip_provider_prefix(model))
        instructions_text = (
            fetch_codex_instructions(normalized_model) if self._codex_mode_enabled else None
        )
        instructions, input_messages = derive_instructions(
            messages,
            codex_mode=self._codex_mode_enabled,
            normalized_model=normalized_model,
            instructions_text=instructions_text,
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
        data = parse_response_body(response)
        return transform_response(data, normalized_model)

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
        chunk = build_streaming_chunk(completion_response)
        stream = (chunk for _ in [0])
        return CustomStreamWrapper(
            stream,
            model,
            logging_obj=logging_obj,
            custom_llm_provider=custom_llm_provider or "codex",
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
        chunk = build_streaming_chunk(completion_response)

        async def async_stream() -> Any:
            yield chunk

        return CustomStreamWrapper(
            async_stream(),
            model,
            logging_obj=logging_obj,
            custom_llm_provider=custom_llm_provider or "codex",
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
        except httpx.RequestError as exc:  # pragma: no cover - network/transport errors
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
        except httpx.RequestError as exc:  # pragma: no cover - network/transport errors
            raise RuntimeError(f"Codex API error: {exc}") from exc

    def _format_http_error(self, response: httpx.Response) -> str:
        detail = ""
        try:
            detail_json = response.json()
            detail = detail_json.get("error", {}).get("message") or detail_json.get("detail", "")
        except ValueError:
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
