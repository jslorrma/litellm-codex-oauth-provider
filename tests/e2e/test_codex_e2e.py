"""End-to-end tests for Codex provider using real API via LiteLLM.

These tests verify real-world functionality against the actual Codex API endpoints.
By default, these tests are SKIPPED to avoid unintended API calls. They should be
manually enabled for testing against live Codex endpoints with valid authentication.

This suite validates:
- Complete completion workflows (sync and async)
- Streaming functionality (sync and async)
- Tool calling capabilities (sync and async)
- Real-world error handling and response validation
"""

from __future__ import annotations

import litellm
import pytest

from litellm_codex_oauth_provider.provider import CodexAuthProvider

# Model definitions for real API testing
REAL_MODELS = [
    "codex/gpt-5.1",
    "codex/gpt-5.1-codex",
    "codex/codex-gpt-5.1-codex-max",
    "codex/gpt-5.1-codex-mini",
]

# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def register_codex_provider() -> CodexAuthProvider:
    """Register Codex provider with LiteLLM for real API calls."""
    provider = CodexAuthProvider()
    litellm.custom_provider_map = [{"provider": "codex", "custom_handler": provider}]
    return provider


@pytest.fixture
def base_message() -> list[dict[str, str]]:
    """Simple user message for basic completion tests."""
    return [{"role": "user", "content": "Say hello and mention Codex."}]


@pytest.fixture
def tool_payload() -> list[dict]:
    """Basic tool definition for testing tool-enabled requests."""
    return [
        {
            "type": "function",
            "function": {
                "name": "bash",
                "description": "Run a bash command",
                "parameters": {
                    "type": "object",
                    "properties": {"command": {"type": "string"}},
                    "required": ["command"],
                },
            },
        }
    ]


# =============================================================================
# TESTS
# =============================================================================


class TestBasicCompletion:
    """Test basic completion functionality without tools."""

    @pytest.mark.skip(reason="Hits real Codex API; enable manually with valid auth")
    @pytest.mark.parametrize("model", REAL_MODELS)
    def test_litellm_completion_real(
        self,
        model: str,
        register_codex_provider: CodexAuthProvider,
        base_message: list[dict[str, str]],
    ) -> None:
        """Given: Valid Codex model and user messages
        When: A synchronous completion request is made to real Codex API
        Then: The provider returns a response with content
        """
        _ = register_codex_provider
        response = litellm.completion(model=model, messages=base_message, max_tokens=128)
        assert response is not None
        assert response.choices and response.choices[0].message.content

    @pytest.mark.skip(reason="Hits real Codex API; enable manually with valid auth")
    @pytest.mark.asyncio
    @pytest.mark.parametrize("model", REAL_MODELS)
    async def test_litellm_acompletion_real(
        self,
        model: str,
        register_codex_provider: CodexAuthProvider,
        base_message: list[dict[str, str]],
    ) -> None:
        """Given: Valid Codex model and user messages
        When: An asynchronous completion request is made to real Codex API
        Then: The provider returns a response with content
        """
        _ = register_codex_provider
        response = await litellm.acompletion(model=model, messages=base_message, max_tokens=128)
        assert response is not None
        assert response.choices and response.choices[0].message.content


class TestStreaming:
    """Test streaming functionality without tools."""

    @pytest.mark.skip(reason="Hits real Codex API; enable manually with valid auth")
    @pytest.mark.parametrize("model", REAL_MODELS)
    def test_litellm_streaming_real(
        self,
        model: str,
        register_codex_provider: CodexAuthProvider,
        base_message: list[dict[str, str]],
    ) -> None:
        """Given: Valid Codex model and user messages
        When: A synchronous streaming request is made to real Codex API
        Then: The provider returns multiple chunks with text content
        """
        _ = register_codex_provider
        chunks = list(
            litellm.streaming(model=model, messages=base_message, max_tokens=64, stream=True)
        )
        assert chunks
        assert any(getattr(chunk, "text", "") for chunk in chunks)

    @pytest.mark.skip(reason="Hits real Codex API; enable manually with valid auth")
    @pytest.mark.asyncio
    @pytest.mark.parametrize("model", REAL_MODELS)
    async def test_litellm_astreaming_real(
        self,
        model: str,
        register_codex_provider: CodexAuthProvider,
        base_message: list[dict[str, str]],
    ) -> None:
        """Given: Valid Codex model and user messages
        When: An asynchronous streaming request is made to real Codex API
        Then: The provider returns multiple chunks with text content
        """
        _ = register_codex_provider
        collected = []
        async for chunk in litellm.astreaming(
            model=model, messages=base_message, max_tokens=64, stream=True
        ):
            collected.append(chunk)
        assert collected
        assert any(getattr(chunk, "text", "") for chunk in collected)


class TestToolCalling:
    """Test functionality with tool calling enabled."""

    @pytest.mark.skip(reason="Hits real Codex API; enable manually with valid auth")
    @pytest.mark.parametrize("model", REAL_MODELS)
    def test_litellm_completion_with_tools_real(
        self,
        model: str,
        register_codex_provider: CodexAuthProvider,
        base_message: list[dict[str, str]],
        tool_payload: list[dict],
    ) -> None:
        """Given: Valid Codex model, user messages, and tool definitions
        When: A synchronous completion request with tools is made to real Codex API
        Then: The provider returns a response with tool_calls
        """
        _ = register_codex_provider
        response = litellm.completion(
            model=model,
            messages=base_message,
            tools=tool_payload,
            tool_choice="auto",
            max_tokens=128,
        )
        assert response is not None
        assert response.choices
        assert response.choices[0].message.tool_calls is not None

    @pytest.mark.skip(reason="Hits real Codex API; enable manually with valid auth")
    @pytest.mark.asyncio
    @pytest.mark.parametrize("model", REAL_MODELS)
    async def test_litellm_acompletion_with_tools_real(
        self,
        model: str,
        register_codex_provider: CodexAuthProvider,
        base_message: list[dict[str, str]],
        tool_payload: list[dict],
    ) -> None:
        """Given: Valid Codex model, user messages, and tool definitions
        When: An asynchronous completion request with tools is made to real Codex API
        Then: The provider returns a response with tool_calls
        """
        _ = register_codex_provider
        response = await litellm.acompletion(
            model=model,
            messages=base_message,
            tools=tool_payload,
            tool_choice="auto",
            max_tokens=128,
        )
        assert response.choices
        assert response.choices[0].message.tool_calls is not None

    @pytest.mark.skip(reason="Hits real Codex API; enable manually with valid auth")
    @pytest.mark.parametrize("model", REAL_MODELS)
    def test_litellm_streaming_with_tools_real(
        self,
        model: str,
        register_codex_provider: CodexAuthProvider,
        base_message: list[dict[str, str]],
        tool_payload: list[dict],
    ) -> None:
        """Given: Valid Codex model, user messages, and tool definitions
        When: A synchronous streaming request with tools is made to real Codex API
        Then: The provider returns chunks containing tool_use information
        """
        _ = register_codex_provider
        chunks = list(
            litellm.streaming(
                model=model,
                messages=base_message,
                tools=tool_payload,
                tool_choice="auto",
                max_tokens=64,
                stream=True,
            )
        )
        assert chunks
        assert any(getattr(chunk, "tool_use", None) for chunk in chunks)

    @pytest.mark.skip(reason="Hits real Codex API; enable manually with valid auth")
    @pytest.mark.asyncio
    @pytest.mark.parametrize("model", REAL_MODELS)
    async def test_litellm_astreaming_with_tools_real(
        self,
        model: str,
        register_codex_provider: CodexAuthProvider,
        base_message: list[dict[str, str]],
        tool_payload: list[dict],
    ) -> None:
        """Given: Valid Codex model, user messages, and tool definitions
        When: An asynchronous streaming request with tools is made to real Codex API
        Then: The provider returns chunks containing tool_use information
        """
        _ = register_codex_provider
        collected = []
        async for chunk in litellm.astreaming(
            model=model,
            messages=base_message,
            tools=tool_payload,
            tool_choice="auto",
            max_tokens=64,
            stream=True,
        ):
            collected.append(chunk)
        assert collected
        assert any(getattr(chunk, "tool_use", None) for chunk in collected)
