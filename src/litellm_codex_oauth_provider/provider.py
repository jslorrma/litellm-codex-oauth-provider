"""Codex OAuth Authentication Provider for LiteLLM.

This module implements a custom LiteLLM provider that uses Codex CLI's OAuth
authentication to access ChatGPT Plus models through OpenAI API.
"""

from __future__ import annotations

import logging
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
from .openai_client import AsyncCodexOpenAIClient, CodexOpenAIClient
from .prompts import DEFAULT_INSTRUCTIONS, build_tool_bridge_message, derive_instructions
from .reasoning import apply_reasoning_config
from .remote_resources import fetch_codex_instructions

logger = logging.getLogger(__name__)


class CodexAuthProvider(CustomLLM):
    """Custom LiteLLM provider that uses Codex CLI's OAuth authentication."""

    def __init__(self) -> None:
        """Initialize the CodexAuthProvider."""
        super().__init__()
        self._maybe_enable_debug_logging()
        self.base_url = self._resolve_base_url(None)
        self._cached_token: str | None = None
        self._token_expiry: float | None = None
        self._account_id: str | None = None
        self._codex_mode_enabled = self._resolve_codex_mode()
        self._client = CodexOpenAIClient(
            token_provider=self.get_bearer_token,
            account_id_provider=self._resolve_account_id,
            base_url=self.base_url,
        )
        self._async_client = AsyncCodexOpenAIClient(
            token_provider=self.get_bearer_token,
            account_id_provider=self._resolve_account_id,
            base_url=self.base_url,
        )

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

    def _resolve_account_id(self) -> str | None:
        if self._account_id:
            return self._account_id
        if self._cached_token:
            return _decode_account_id(self._cached_token)
        return None

    def _resolve_base_url(self, api_base: str | None) -> str:
        base = (api_base or constants.CODEX_API_BASE_URL).rstrip("/")
        if base.endswith(constants.CODEX_RESPONSES_ENDPOINT):
            base = base[: -len(constants.CODEX_RESPONSES_ENDPOINT)]
        if base.endswith(constants.OPENAI_RESPONSES_ENDPOINT):
            base = base[: -len(constants.OPENAI_RESPONSES_ENDPOINT)]
        if not base.endswith("/codex"):
            base = f"{base}/codex"
        return base

    def _resolve_codex_mode(self) -> bool:
        """Resolve CODEX_MODE feature flag."""
        env_value = os.getenv(constants.CODEX_MODE_ENV)
        if env_value is None:
            return constants.DEFAULT_CODEX_MODE
        return env_value.strip().lower() not in {"0", "false", "off"}

    def _maybe_enable_debug_logging(self) -> None:
        if os.getenv("CODEX_DEBUG", "").lower() in {"1", "true", "yes", "on", "debug"}:
            logging.basicConfig(level=logging.DEBUG)
            logger.debug("CODEX_DEBUG enabled; debug logging active.")

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
        optional_params = kwargs.pop("optional_params", {}) or {}
        normalized_tools = self._normalize_tools(
            kwargs.pop("tools", None) or optional_params.pop("tools", None)
        )
        merged_options = {**optional_params, **kwargs}

        payload: dict[str, Any] = {
            "model": model,
            "input": self._prepare_input(messages=messages, tools=normalized_tools),
            "instructions": instructions or DEFAULT_INSTRUCTIONS,
            "include": [constants.REASONING_INCLUDE_TARGET],
            "store": False,
            **reasoning_config,
        }

        if normalized_tools:
            payload["tools"] = normalized_tools

        payload.update(self._filter_payload_options(merged_options))

        if prompt_cache_key:
            payload["prompt_cache_key"] = prompt_cache_key

        return payload

    def _build_extra_headers(self, prompt_cache_key: str | None) -> dict[str, str]:
        headers: dict[str, str] = {
            "accept": "text/event-stream",
            "Content-Type": "application/json",
            constants.OPENAI_BETA_HEADER: constants.OPENAI_BETA_VALUE,
            constants.OPENAI_ORIGINATOR_HEADER: constants.OPENAI_ORIGINATOR_VALUE,
        }
        account_id = self._resolve_account_id()
        if account_id:
            headers[constants.CHATGPT_ACCOUNT_HEADER] = account_id
        if prompt_cache_key:
            headers[constants.SESSION_ID_HEADER] = prompt_cache_key
            headers[constants.CONVERSATION_ID_HEADER] = prompt_cache_key
        return headers

    def _prepare_input(
        self, *, messages: list[dict[str, Any]], tools: list[dict[str, Any]] | None
    ) -> list[dict[str, Any]]:
        """Return Codex-ready input, optionally prepending the bridge prompt when tools are used."""
        input_messages = list(messages)
        if self._codex_mode_enabled and tools:
            input_messages = [build_tool_bridge_message(), *input_messages]
        return input_messages

    def _get_sync_client(self, base_url: str) -> CodexOpenAIClient:
        if base_url == self.base_url:
            return self._client
        return CodexOpenAIClient(
            token_provider=self.get_bearer_token,
            account_id_provider=self._resolve_account_id,
            base_url=base_url,
        )

    def _get_async_client(self, base_url: str) -> AsyncCodexOpenAIClient:
        if base_url == self.base_url:
            return self._async_client
        return AsyncCodexOpenAIClient(
            token_provider=self.get_bearer_token,
            account_id_provider=self._resolve_account_id,
            base_url=base_url,
        )

    @staticmethod
    def _filter_payload_options(options: Mapping[str, Any]) -> dict[str, Any]:
        """Allow only Response API-supported parameters, remapping when needed."""
        passthrough_keys = {
            "metadata",
            "parallel_tool_calls",
            "prompt",
            "previous_response_id",
            "tool_choice",
            "user",
        }
        passthrough = {
            key: value
            for key, value in options.items()
            if key in passthrough_keys and value is not None
        }

        # These parameters are accepted for OpenAI compatibility, but are filtered out before sending to Codex,
        # since Codex does not support them. This allows the provider to maintain API signature parity with OpenAI,
        # while preventing 400 errors from unsupported parameters.
        unsupported = {
            "max_tokens",
            "max_output_tokens",
            "temperature",
            "safety_identifier",
            "prompt_cache_retention",
            "truncation",
            "top_logprobs",
            "top_p",
            "service_tier",
            "max_tool_calls",
            "background",
        }

        if logger.isEnabledFor(logging.DEBUG):
            dropped = sorted(set(options).intersection(unsupported))
            if dropped:
                logger.debug("Dropped unsupported response params", extra={"keys": dropped})

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
                tool_dict.setdefault("strict", function_payload.get("strict"))
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
        base_url = self._resolve_base_url(api_base)
        self.get_bearer_token()

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
        headers = self._build_extra_headers(prompt_cache_key)
        data = self._dispatch_response_request(
            payload=payload, extra_headers=headers, base_url=base_url
        )
        return transform_response(data, normalized_model)

    async def acompletion(
        self, model: str, messages: list[dict[str, Any]], api_base: str | None = None, **kwargs: Any
    ) -> ModelResponse:
        """Async completion for LiteLLM usage."""
        kwargs = dict(kwargs)
        prompt_cache_key = kwargs.pop("prompt_cache_key", None)
        base_url = self._resolve_base_url(api_base)
        self.get_bearer_token()

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
        headers = self._build_extra_headers(prompt_cache_key)

        data = await self._dispatch_response_request_async(
            payload=payload, extra_headers=headers, base_url=base_url
        )
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

    def _dispatch_response_request(
        self, *, payload: dict[str, Any], extra_headers: dict[str, str], base_url: str
    ) -> dict[str, Any]:
        client = self._get_sync_client(base_url)
        self._log_request_debug(base_url, payload, extra_headers)
        return self._dispatch_via_httpx(client=client, payload=payload, extra_headers=extra_headers)

    async def _dispatch_response_request_async(
        self, *, payload: dict[str, Any], extra_headers: dict[str, str], base_url: str
    ) -> dict[str, Any]:
        client = self._get_async_client(base_url)
        self._log_request_debug(base_url, payload, extra_headers)
        return await self._dispatch_via_httpx_async(
            client=client, payload=payload, extra_headers=extra_headers
        )

    def _log_request_debug(
        self, base_url: str, payload: Mapping[str, Any], extra_headers: Mapping[str, str]
    ) -> None:
        if not logger.isEnabledFor(logging.DEBUG):
            return
        sanitized_headers = {
            key: ("***" if key.lower() == "authorization" else value)
            for key, value in extra_headers.items()
        }
        model = payload.get("model")
        prompt_cache_key = payload.get("prompt_cache_key")
        include = payload.get("include")
        reasoning = payload.get("reasoning")
        tools = payload.get("tools") or []
        input_messages = payload.get("input") or []
        logger.debug(
            "Dispatching Codex responses request",
            extra={
                "base_url": base_url,
                "model": model,
                "input_len": len(input_messages),
                "tools_len": len(tools),
                "include": include,
                "prompt_cache_key": prompt_cache_key,
                "reasoning": reasoning,
                "headers": sanitized_headers,
            },
        )

    def _dispatch_via_httpx(
        self,
        *,
        client: CodexOpenAIClient,
        payload: Mapping[str, Any],
        extra_headers: Mapping[str, str],
    ) -> dict[str, Any]:
        payload_with_stream = dict(payload)
        payload_with_stream.setdefault("stream", True)
        headers = {
            **extra_headers,
            "Accept": "text/event-stream",
            "Content-Type": "application/json",
        }
        headers.setdefault("Authorization", client.auth_headers.get("Authorization", ""))
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug(
                "Fallback POST via httpx",
                extra={
                    "url": "/responses",
                    "headers": {
                        k: ("***" if k.lower() == "authorization" else v)
                        for k, v in headers.items()
                    },
                    "payload_keys": sorted(payload_with_stream.keys()),
                },
            )

        response = client.http_client.post(  # type: ignore[attr-defined]
            "/responses",
            json=payload_with_stream,
            headers=headers,
        )
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            sanitized_headers = {
                key: ("***" if key.lower() == "authorization" else value)
                for key, value in headers.items()
            }
            logger.warning(
                "HTTPX fallback failed",
                extra={
                    "status_code": exc.response.status_code,
                    "body": exc.response.text[:1000],
                    "response_headers": dict(exc.response.headers),
                    "request_headers": sanitized_headers,
                    "payload": payload_with_stream,
                },
            )
            raise
        return parse_response_body(response)

    async def _dispatch_via_httpx_async(
        self,
        *,
        client: AsyncCodexOpenAIClient,
        payload: Mapping[str, Any],
        extra_headers: Mapping[str, str],
    ) -> dict[str, Any]:
        payload_with_stream = dict(payload)
        payload_with_stream.setdefault("stream", True)
        headers = {
            **extra_headers,
            "Accept": "text/event-stream",
            "Content-Type": "application/json",
        }
        headers.setdefault("Authorization", client.auth_headers.get("Authorization", ""))

        response = await client.http_client.post(  # type: ignore[attr-defined]
            "/responses",
            json=payload_with_stream,
            headers=headers,
        )
        response.raise_for_status()
        return parse_response_body(response)

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
