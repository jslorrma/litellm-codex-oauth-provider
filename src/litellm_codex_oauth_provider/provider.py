"""LiteLLM provider that routes completions through Codex OAuth.

This module implements the production-ready `CodexAuthProvider`, a CustomLLM provider
that speaks the OpenAI `/responses` API while authenticating with Codex CLI OAuth
tokens. It centralizes model normalization, prompt preparation, token refresh, request
dispatch, and response adaptation so callers can treat Codex-backed models as if they
were first-class LiteLLM providers.

Architecture overview
---------------------
1. **Authentication**: Access tokens and account IDs are read from the Codex auth file
   and refreshed automatically when they near expiry. Tokens are cached in-memory with
   configurable buffer windows.
2. **Request preparation**: Messages are converted into Codex-ready input, optional tool
   bridge prompts are injected, and instructions are derived from user/system messages.
   Reasoning and verbosity flags are normalized to Codex parameters.
3. **Dispatch**: Payloads are sent via the OpenAI Python client with Codex-specific
   headers. If streaming through the client fails, an httpx fallback posts directly to
   `/responses`. Requests are logged at DEBUG with sensitive fields sanitized.
4. **Response adaptation**: OpenAI-typed models validate payloads when possible, then
   responses are normalized into LiteLLM `ModelResponse` instances for both sync and
   async callers. A small helper produces synthetic streaming chunks for LiteLLM's
   streaming interface.

Usage example
-------------
>>> from litellm_codex_oauth_provider import provider
>>> llm = provider.CodexAuthProvider()
>>> result = llm.completion(
...     model="codex/gpt-5.1-codex",
...     messages=[{"role": "user", "content": "Hello"}],
... )
>>> print(result.choices[0].message.content)

Notes
-----
- Codex mode is always enabled; no additional flags are required.
- The provider is thread-safe and caches tokens per instance.
- Unsupported OpenAI parameters are filtered to avoid 400 responses from Codex.
- Debug logging is opt-in via the `CODEX_DEBUG` environment variable.

See Also
--------
- `adapter`: Response parsing and normalization helpers
- `openai_client`: Codex-aware OpenAI client wrappers
- `auth`: Token reading and refresh utilities
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
from .model_map import _strip_provider_prefix, normalize_model
from .openai_client import AsyncCodexOpenAIClient, CodexOpenAIClient
from .prompts import DEFAULT_INSTRUCTIONS, build_tool_bridge_message, derive_instructions
from .reasoning import apply_reasoning_config
from .remote_resources import fetch_codex_instructions

logger = logging.getLogger(__name__)


class CodexAuthProvider(CustomLLM):
    """Custom LiteLLM provider that uses Codex CLI's OAuth authentication.

    This class implements the CustomLLM interface to provide seamless integration
    between LiteLLM and Codex CLI authentication. It handles the complete request/
    response lifecycle including token management, model normalization, payload
    transformation, and response adaptation.

    The provider supports both synchronous and asynchronous operations, streaming
    responses, tool calling, and comprehensive error handling. It automatically
    manages OAuth tokens, applies reasoning configurations, and provides detailed
    logging for debugging.

    Attributes
    ----------
    base_url : str
        The resolved base URL for Codex API endpoints
    cached_token : str | None
        Cached bearer token for authentication
    token_expiry : float | None
        Timestamp when cached token expires
    account_id : str | None
        Cached ChatGPT account ID from JWT claims

    Examples
    --------
    Basic usage:

    >>> from litellm_codex_oauth_provider import CodexAuthProvider
    >>> provider = CodexAuthProvider()
    >>> response = provider.completion(
    ...     model="codex/gpt-5.1-codex", messages=[{"role": "user", "content": "Hello"}]
    ... )

    With LiteLLM integration:

    >>> import litellm
    >>> from litellm_codex_oauth_provider import CodexAuthProvider
    >>> litellm.register_provider("codex", CodexAuthProvider())
    >>> response = litellm.completion(
    ...     model="codex/gpt-5.1-codex-max",
    ...     messages=[{"role": "user", "content": "Explain quantum computing"}],
    ... )

    Async usage:

    >>> import asyncio
    >>> async def main():
    ...     provider = CodexAuthProvider()
    ...     response = await provider.acompletion(
    ...         model="codex/gpt-5.1-codex", messages=[{"role": "user", "content": "Hello"}]
    ...     )
    ...     return response
    >>> # asyncio.run(main())

    With tool calling:

    >>> tools = [
    ...     {
    ...         "type": "function",
    ...         "function": {
    ...             "name": "get_weather",
    ...             "description": "Get weather information",
    ...             "parameters": {
    ...                 "type": "object",
    ...                 "properties": {"location": {"type": "string"}},
    ...             },
    ...         },
    ...     }
    ... ]
    >>> response = provider.completion(
    ...     model="codex/gpt-5.1-codex-max",
    ...     messages=[{"role": "user", "content": "What's the weather?"}],
    ...     tools=tools,
    ...     tool_choice="auto",
    ... )

    Notes
    -----
    - Requires Codex CLI authentication via 'codex login'
    - Automatically handles token refresh and caching
    - Supports all GPT-5.1 Codex model variants
    - Provides streaming via Server-Sent Events
    - Thread-safe for concurrent usage
    - Detailed logging available via CODEX_DEBUG=1

    See Also
    --------
    - `completion`: Synchronous completion method
    - `acompletion`: Asynchronous completion method
    - `streaming`: Streaming response method
    - `astreaming`: Async streaming response method
    """

    def __init__(self) -> None:
        """Initialize the CodexAuthProvider.

        Sets up the provider with default configuration, initializes OpenAI clients,
        resolves base URL and mode settings, and prepares for authentication.

        The initialization process:
        1. Enables debug logging if CODEX_DEBUG is set
        2. Resolves the base URL for Codex API endpoints
        3. Initializes synchronous and asynchronous OpenAI clients
        4. Sets up token caching and account ID resolution
        5. Resolves Codex mode feature flag

        Examples
        --------
        >>> provider = CodexAuthProvider()
        >>> print(f"Base URL: {provider.base_url}")
        Base URL: https://chatgpt.com/backend-api/codex
        """
        super().__init__()
        self._maybe_enable_debug_logging()
        self.base_url = self._resolve_base_url(None)
        self._cached_token: str | None = None
        self._token_expiry: float | None = None
        self._account_id: str | None = None
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
        """Resolve the ChatGPT account ID from cached state or JWT claims.

        Returns
        -------
        str | None
            The account identifier if available, otherwise ``None``. Cached values are
            preferred to avoid redundant JWT decoding work.

        Notes
        -----
        - Falls back to decoding the cached bearer token when account ID has not been
          resolved yet.
        - Returns ``None`` if no token is cached or decoding fails silently upstream.
        """
        if self._account_id:
            return self._account_id
        if self._cached_token:
            return _decode_account_id(self._cached_token)
        return None

    def _resolve_base_url(self, api_base: str | None) -> str:
        """Normalize the Codex base URL, ensuring the `/codex` prefix is present.

        Parameters
        ----------
        api_base : str | None
            Optional override provided by LiteLLM caller. When ``None`` the default
            Codex API base is used.

        Returns
        -------
        str
            Sanitized base URL without duplicated `/responses` suffix and with a
            trailing `/codex` segment guaranteed.
        """
        base = (api_base or constants.CODEX_API_BASE_URL).rstrip("/")
        if base.endswith(constants.CODEX_RESPONSES_ENDPOINT):
            base = base[: -len(constants.CODEX_RESPONSES_ENDPOINT)]
        if base.endswith(constants.OPENAI_RESPONSES_ENDPOINT):
            base = base[: -len(constants.OPENAI_RESPONSES_ENDPOINT)]
        if not base.endswith("/codex"):
            base = f"{base}/codex"
        return base

    def _maybe_enable_debug_logging(self) -> None:
        """Enable debug logging when `CODEX_DEBUG` is set."""
        if os.getenv("CODEX_DEBUG", "").lower() in {"1", "true", "yes", "on", "debug"}:
            logging.basicConfig(level=logging.DEBUG)
            logger.debug("CODEX_DEBUG enabled; debug logging active.")

    def get_bearer_token(self) -> str:
        """Return a valid Codex bearer token, refreshing if necessary.

        Returns
        -------
        str
            Active bearer token for Codex API calls.

        Raises
        ------
        CodexAuthTokenExpiredError
            If the cached token is expired and refresh fails.

        Notes
        -----
        - Tokens are cached in-memory with a buffer window to avoid expiry mid-request.
        - On expiry, a refresh attempt is performed before propagating the original
          `CodexAuthTokenExpiredError`.
        """
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
        """Construct the Codex `/responses` payload.

        Parameters
        ----------
        model : str
            Normalized Codex model identifier.
        instructions : str
            Instruction string derived from system/user prompts.
        messages : list[dict[str, Any]]
            Chat messages prepared for Codex, optionally prefixed with the tool bridge
            prompt.
        prompt_cache_key : str | None
            Optional cache key to reuse prompt context server-side.
        reasoning_config : dict[str, Any]
            Reasoning and verbosity options normalized for Codex.
        **kwargs : Any
            Additional completion parameters forwarded from LiteLLM.

        Returns
        -------
        dict[str, Any]
            Fully prepared payload ready for dispatch to `/responses`.

        Notes
        -----
        - Unsupported options are filtered later by `_filter_payload_options`.
        - Tool definitions are normalized to match OpenAI tool schema expectations.
        - Prompt cache keys are included in both payload and headers when provided.
        """
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
        """Build Codex-specific headers for `/responses` requests.

        Parameters
        ----------
        prompt_cache_key : str | None
            Optional cache key used to propagate session identifiers for prompt caching.

        Returns
        -------
        dict[str, str]
            Headers including beta flags, originator, account ID, and optional session
            identifiers.
        """
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
        """Return Codex-ready input, optionally prepending the bridge prompt when tools are used.

        Parameters
        ----------
        messages : list[dict[str, Any]]
            Chat messages provided by the caller.
        tools : list[dict[str, Any]] | None
            Normalized tool definitions. When present, a tool bridge system message is
            injected to align Codex tool calling with OpenAI semantics.

        Returns
        -------
        list[dict[str, Any]]
            Input message list ready for inclusion in the `/responses` payload.
        """
        input_messages = list(messages)
        if tools:
            input_messages = [build_tool_bridge_message(), *input_messages]
        return input_messages

    def _get_sync_client(self, base_url: str) -> CodexOpenAIClient:
        """Return a CodexOpenAIClient targeting the requested base URL."""
        if base_url == self.base_url:
            return self._client
        return CodexOpenAIClient(
            token_provider=self.get_bearer_token,
            account_id_provider=self._resolve_account_id,
            base_url=base_url,
        )

    def _get_async_client(self, base_url: str) -> AsyncCodexOpenAIClient:
        """Return an AsyncCodexOpenAIClient targeting the requested base URL."""
        if base_url == self.base_url:
            return self._async_client
        return AsyncCodexOpenAIClient(
            token_provider=self.get_bearer_token,
            account_id_provider=self._resolve_account_id,
            base_url=base_url,
        )

    @staticmethod
    def _filter_payload_options(options: Mapping[str, Any]) -> dict[str, Any]:
        """Allow only Response API-supported parameters, remapping when needed.

        Parameters
        ----------
        options : Mapping[str, Any]
            Raw keyword arguments provided to the completion call.

        Returns
        -------
        dict[str, Any]
            Filtered parameters safe to send to the Codex `/responses` endpoint.

        Notes
        -----
        Unsupported OpenAI parameters are intentionally dropped to avoid 400 responses.
        A DEBUG log entry lists any dropped keys for troubleshooting.
        """
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
        """Normalize tool definitions to OpenAI-compliant schema.

        Parameters
        ----------
        tools : Any
            Raw tool definitions supplied to LiteLLM.

        Returns
        -------
        list[dict[str, Any]] | None
            Normalized tool list or ``None`` when no tools are provided.

        Raises
        ------
        ValueError
            If tool definitions are not provided as a list or required names are missing.
        """
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
        """Complete a chat completion request using Codex authentication.

        This method implements the synchronous completion interface required by LiteLLM's
        CustomLLM. It handles the complete request lifecycle including model normalization,
        instruction derivation, payload construction, API dispatch, and response transformation.

        Parameters
        ----------
        model : str
            The model identifier. Supports various formats including provider prefixes
            (e.g., "codex/gpt-5.1-codex", "codex-oauth/gpt-5.1-codex-max") and effort
            suffixes (e.g., "-high", "-medium", "-xhigh").
        messages : list[dict[str, Any]]
            List of chat messages in OpenAI format. Each message should have 'role'
            (system, user, assistant, tool) and 'content' keys. Tool messages should
            include 'tool_call_id' and 'content'.
        api_base : str | None, optional
            Custom API base URL. If None, uses the default Codex API endpoint.
        custom_llm_provider : str | None, optional
            Custom provider identifier (reserved for LiteLLM interface compatibility).
        **kwargs : Any
            Additional parameters including:
            - tools: List of tool definitions for function calling
            - tool_choice: Tool selection strategy ("auto", "required", "none")
            - metadata: Additional metadata to include in the request
            - user: User identifier for the request
            - reasoning_effort: Reasoning effort level ("none", "minimal", "low", "medium", "high", "xhigh")
            - verbosity: Response verbosity level
            - prompt_cache_key: Cache key for prompt caching

        Returns
        -------
        ModelResponse
            LiteLLM-compatible response object containing the completion result,
            usage statistics, and metadata.

        Raises
        ------
        CodexAuthFileNotFoundError
            If Codex CLI authentication file is not found.
        CodexAuthTokenExpiredError
            If the authentication token has expired.
        RuntimeError
            If the API request fails or response parsing fails.

        Examples
        --------
        Basic completion:

        >>> provider = CodexAuthProvider()
        >>> response = provider.completion(
        ...     model="codex/gpt-5.1-codex", messages=[{"role": "user", "content": "Hello, world!"}]
        ... )
        >>> print(response.choices[0].message.content)

        With custom API base:

        >>> response = provider.completion(
        ...     model="gpt-5.1-codex",
        ...     messages=[{"role": "user", "content": "Explain quantum computing"}],
        ...     api_base="https://custom.endpoint.com",
        ... )

        With tool calling:

        >>> tools = [
        ...     {
        ...         "type": "function",
        ...         "function": {
        ...             "name": "get_weather",
        ...             "description": "Get weather for a location",
        ...             "parameters": {
        ...                 "type": "object",
        ...                 "properties": {
        ...                     "location": {"type": "string", "description": "City name"}
        ...                 },
        ...             },
        ...         },
        ...     }
        ... ]
        >>> response = provider.completion(
        ...     model="codex/gpt-5.1-codex-max",
        ...     messages=[{"role": "user", "content": "What's the weather in Paris?"}],
        ...     tools=tools,
        ...     tool_choice="auto",
        ... )

        With reasoning configuration:

        >>> response = provider.completion(
        ...     model="codex/gpt-5.1-codex-high",
        ...     messages=[{"role": "user", "content": "Analyze this complex problem"}],
        ...     reasoning_effort="high",
        ...     verbosity="high",
        ... )

        Notes
        -----
        - The method automatically handles token refresh if needed
        - Model names are normalized to Codex-compatible identifiers
        - System messages are converted to Codex instructions
        - Tool bridge prompts are automatically added when tools are present
        - Unsupported parameters are filtered out to prevent API errors
        - Detailed logging is available when CODEX_DEBUG=1

        See Also
        --------
        - `acompletion`: Asynchronous version of this method
        - `streaming`: Streaming version of this method
        - `normalize_model`: Model name normalization
        - `derive_instructions`: Message to instruction conversion
        """
        _ = custom_llm_provider  # parameter reserved by LiteLLM interface

        kwargs = dict(kwargs)
        prompt_cache_key = kwargs.pop("prompt_cache_key", None)
        base_url = self._resolve_base_url(api_base)
        self.get_bearer_token()

        normalized_model = normalize_model(_strip_provider_prefix(model))
        instructions_text = fetch_codex_instructions(normalized_model)
        instructions, input_messages = derive_instructions(
            messages,
            normalized_model=normalized_model,
            instructions_text=instructions_text,
        )
        reasoning_config = apply_reasoning_config(
            original_model=_strip_provider_prefix(model),
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
        """Async completion for LiteLLM usage.

        Parameters
        ----------
        model : str
            Requested model identifier (provider prefix optional).
        messages : list[dict[str, Any]]
            Chat history in OpenAI format.
        api_base : str | None, optional
            Optional Codex base URL override.
        **kwargs : Any
            Additional completion parameters mirrored from `completion`.

        Returns
        -------
        ModelResponse
            Parsed and normalized completion result.

        Notes
        -----
        Follows the same preparation and dispatch pipeline as `completion` but uses the
        asynchronous OpenAI client and httpx transport.
        """
        kwargs = dict(kwargs)
        prompt_cache_key = kwargs.pop("prompt_cache_key", None)
        base_url = self._resolve_base_url(api_base)
        self.get_bearer_token()

        normalized_model = normalize_model(_strip_provider_prefix(model))
        instructions_text = fetch_codex_instructions(normalized_model)
        instructions, input_messages = derive_instructions(
            messages,
            normalized_model=normalized_model,
            instructions_text=instructions_text,
        )
        reasoning_config = apply_reasoning_config(
            original_model=_strip_provider_prefix(model),
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
        """Simulate streaming by emitting a single generic streaming chunk.

        Parameters
        ----------
        model : str
            Requested model identifier.
        messages : list[dict[str, Any]]
            Chat messages in OpenAI format.
        api_base : str | None, optional
            Codex base URL override.
        custom_llm_provider : str | None, optional
            LiteLLM provider identifier (ignored but preserved for signature parity).
        **kwargs : Any
            Additional completion parameters forwarded to `completion`.

        Returns
        -------
        CustomStreamWrapper
            Iterable producing a single streaming chunk compatible with LiteLLM.
        """
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
        """Simulate async streaming by emitting a single generic streaming chunk.

        Parameters
        ----------
        model : str
            Requested model identifier.
        messages : list[dict[str, Any]]
            Chat messages in OpenAI format.
        api_base : str | None, optional
            Codex base URL override.
        custom_llm_provider : str | None, optional
            LiteLLM provider identifier (ignored but preserved for signature parity).
        **kwargs : Any
            Additional completion parameters forwarded to `acompletion`.

        Returns
        -------
        CustomStreamWrapper
            Async iterable producing a single streaming chunk compatible with LiteLLM.
        """
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
        """Dispatch a `/responses` request synchronously via httpx fallback.

        Parameters
        ----------
        payload : dict[str, Any]
            Prepared request body.
        extra_headers : dict[str, str]
            Headers including beta flags and optional session identifiers.
        base_url : str
            Target Codex base URL.

        Returns
        -------
        dict[str, Any]
            Parsed JSON response body.
        """
        client = self._get_sync_client(base_url)
        self._log_request_debug(base_url, payload, extra_headers)
        return self._dispatch_via_httpx(client=client, payload=payload, extra_headers=extra_headers)

    async def _dispatch_response_request_async(
        self, *, payload: dict[str, Any], extra_headers: dict[str, str], base_url: str
    ) -> dict[str, Any]:
        """Dispatch a `/responses` request asynchronously via httpx fallback.

        Parameters
        ----------
        payload : dict[str, Any]
            Prepared request body.
        extra_headers : dict[str, str]
            Headers including beta flags and optional session identifiers.
        base_url : str
            Target Codex base URL.

        Returns
        -------
        dict[str, Any]
            Parsed JSON response body.
        """
        client = self._get_async_client(base_url)
        self._log_request_debug(base_url, payload, extra_headers)
        return await self._dispatch_via_httpx_async(
            client=client, payload=payload, extra_headers=extra_headers
        )

    def _log_request_debug(
        self, base_url: str, payload: Mapping[str, Any], extra_headers: Mapping[str, str]
    ) -> None:
        """Emit sanitized DEBUG logging for outbound requests.

        Parameters
        ----------
        base_url : str
            Target Codex base URL.
        payload : Mapping[str, Any]
            Prepared request payload.
        extra_headers : Mapping[str, str]
            Headers to be sent with the request.
        """
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
        """Send the request via httpx using the synchronous client.

        Parameters
        ----------
        client : CodexOpenAIClient
            Prepared sync OpenAI client.
        payload : Mapping[str, Any]
            Request payload.
        extra_headers : Mapping[str, str]
            Additional headers to merge into the request.

        Returns
        -------
        dict[str, Any]
            Parsed JSON response from Codex.

        Raises
        ------
        httpx.HTTPStatusError
            If the Codex API returns a non-success status code.
        """
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
        """Send the request via httpx using the asynchronous client.

        Parameters
        ----------
        client : AsyncCodexOpenAIClient
            Prepared async OpenAI client.
        payload : Mapping[str, Any]
            Request payload.
        extra_headers : Mapping[str, str]
            Additional headers to merge into the request.

        Returns
        -------
        dict[str, Any]
            Parsed JSON response from Codex.

        Raises
        ------
        httpx.HTTPStatusError
            If the Codex API returns a non-success status code.
        """
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
        """Render a descriptive error message from an httpx response.

        Parameters
        ----------
        response : httpx.Response
            Response received from the Codex API.

        Returns
        -------
        str
            Human-readable error summary including status, detail message, and
            rate-limit hints when available.
        """
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
