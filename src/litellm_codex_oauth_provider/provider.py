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

import logging
import os
import time
from collections.abc import Mapping
from typing import Any

from litellm import CustomLLM, ModelResponse
from litellm.types.utils import GenericStreamingChunk
from litellm.utils import CustomStreamWrapper

from . import constants
from .adapter import transform_response
from .auth import _decode_account_id, get_auth_context
from .exceptions import CodexAuthTokenExpiredError
from .http_client import SimpleCodexClient
from .model_map import _strip_provider_prefix, normalize_model
from .prompts import DEFAULT_INSTRUCTIONS, build_tool_bridge_message, derive_instructions
from .reasoning import apply_reasoning_config
from .remote_resources import fetch_codex_instructions

logger = logging.getLogger(__name__)


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

        # Initialize simple HTTP client
        self._http_client = SimpleCodexClient(
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

    def _normalize_model(self, model: str) -> str:
        """Normalize model name for Codex API."""
        return normalize_model(_strip_provider_prefix(model))

    def _prepare_messages(
        self, messages: list[dict[str, Any]], tools: list[dict[str, Any]] | None = None
    ) -> list[dict[str, Any]]:
        """Prepare messages with optional tool bridge injection."""
        input_messages = list(messages)
        if tools:
            input_messages = [build_tool_bridge_message(), *input_messages]
        return input_messages

    def _build_payload(
        self,
        model: str,
        instructions: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Build the Codex responses API payload."""
        payload = {
            "model": model,
            "input": self._prepare_messages(messages, tools),
            "instructions": instructions or DEFAULT_INSTRUCTIONS,
            "include": [constants.REASONING_INCLUDE_TARGET],
            "store": False,
        }

        # Add tools if provided
        if tools:
            payload["tools"] = tools

        # Add reasoning config
        reasoning_config = apply_reasoning_config(
            original_model=_strip_provider_prefix(model),
            normalized_model=model,
            reasoning_effort=kwargs.get("reasoning_effort"),
            verbosity=kwargs.get("verbosity"),
        )
        payload.update(reasoning_config)

        # Add basic passthrough options
        optional_params = kwargs.get("optional_params", {}) or {}
        passthrough = {
            "metadata": optional_params.get("metadata"),
            "user": optional_params.get("user"),
        }
        payload.update({k: v for k, v in passthrough.items() if v is not None})

        return payload

    def _dispatch_request(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Dispatch request using the simple HTTP client."""
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug(
                "Dispatching Codex responses request",
                extra={
                    "model": payload.get("model"),
                    "input_len": len(payload.get("input", [])),
                    "tools_len": len(payload.get("tools", [])),
                },
            )

        return self._http_client.post_responses(payload)

    async def _dispatch_request_async(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Dispatch async request using the simple HTTP client."""
        return await self._http_client.post_responses_async(payload)

    def completion(
        self,
        model: str,
        messages: list[dict[str, Any]],
        **kwargs: Any,
    ) -> ModelResponse:
        """Complete a chat completion request using Codex authentication.

        Parameters
        ----------
        model : str
            Model identifier (supports provider prefixes like "codex/")
        messages : list[dict[str, Any]]
            Chat messages in OpenAI format
        **kwargs : Any
            Additional parameters including tools, reasoning_effort, verbosity, etc.

        Returns
        -------
        ModelResponse
            LiteLLM-compatible response object
        """
        # Normalize model name
        normalized_model = self._normalize_model(model)

        # Get instructions and prepare messages
        instructions_text = fetch_codex_instructions(normalized_model)
        instructions, prepared_messages = derive_instructions(
            messages,
            normalized_model=normalized_model,
            instructions_text=instructions_text,
        )

        # Extract tools
        optional_params = kwargs.get("optional_params", {}) or {}
        tools = kwargs.get("tools") or optional_params.get("tools")
        normalized_tools = self._normalize_tools(tools) if tools else None

        # Build payload
        payload = self._build_payload(
            model=normalized_model,
            instructions=instructions,
            messages=prepared_messages,
            tools=normalized_tools,
            **kwargs,
        )

        # Dispatch request and transform response
        data = self._dispatch_request(payload)
        return transform_response(data, normalized_model)

    async def acompletion(
        self,
        model: str,
        messages: list[dict[str, Any]],
        **kwargs: Any,
    ) -> ModelResponse:
        """Async completion method.

        Parameters and returns follow the same pattern as completion().
        """
        # Normalize model name
        normalized_model = self._normalize_model(model)

        # Get instructions and prepare messages
        instructions_text = fetch_codex_instructions(normalized_model)
        instructions, prepared_messages = derive_instructions(
            messages,
            normalized_model=normalized_model,
            instructions_text=instructions_text,
        )

        # Extract tools
        optional_params = kwargs.get("optional_params", {}) or {}
        tools = kwargs.get("tools") or optional_params.get("tools")
        normalized_tools = self._normalize_tools(tools) if tools else None

        # Build payload
        payload = self._build_payload(
            model=normalized_model,
            instructions=instructions,
            messages=prepared_messages,
            tools=normalized_tools,
            **kwargs,
        )

        # Dispatch async request and transform response
        data = await self._dispatch_request_async(payload)
        return transform_response(data, normalized_model)

    def streaming(
        self,
        model: str,
        messages: list[dict[str, Any]],
        **kwargs: Any,
    ) -> CustomStreamWrapper:
        """Return a streaming response wrapper.

        For simplicity, this implementation provides non-streaming responses
        wrapped in streaming format. True streaming will be implemented in a later iteration.
        """
        # Get the completion response
        response = self.completion(model, messages, **kwargs)

        # Create a simple streaming chunk
        chunk_data = {
            "text": response.choices[0].message.content or "",
            "is_finished": True,
            "finish_reason": response.choices[0].finish_reason or "stop",
            "index": 0,
            "usage": response.usage,
            "provider_specific_fields": {
                "id": response.id,
                "model": response.model,
            },
        }

        chunk = GenericStreamingChunk(**chunk_data)

        # Return single-chunk stream
        stream = (chunk for _ in [0])
        return CustomStreamWrapper(
            stream,
            model,
            logging_obj=kwargs.get("logging_obj"),
            custom_llm_provider="codex",
        )

    async def astreaming(
        self,
        model: str,
        messages: list[dict[str, Any]],
        **kwargs: Any,
    ) -> CustomStreamWrapper:
        """Async streaming response wrapper.

        Returns a streaming wrapper with a single chunk containing the full response.
        """
        # Get the async completion response
        response = await self.acompletion(model, messages, **kwargs)

        # Create a simple streaming chunk
        chunk = GenericStreamingChunk(
            text=response.choices[0].message.content or "",
            is_finished=True,
            finish_reason=response.choices[0].finish_reason or "stop",
            index=0,
            usage=response.usage,
            provider_specific_fields={
                "id": response.id,
                "model": response.model,
            },
        )

        # Create async stream
        async def async_stream() -> Any:
            yield chunk

        return CustomStreamWrapper(
            async_stream(),
            model,
            logging_obj=kwargs.get("logging_obj"),
            custom_llm_provider="codex",
        )

    @staticmethod
    def _normalize_tools(tools: list[dict[str, Any]] | None) -> list[dict[str, Any]] | None:
        """Normalize tool definitions to OpenAI-compliant schema.

        Simplified version that handles the basic case without excessive validation.
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


# Global instance for LiteLLM compatibility
codex_auth_provider = CodexAuthProvider()
