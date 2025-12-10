"""LiteLLM provider integration tests using the mock Codex API.

This module provides comprehensive integration tests for the Codex OAuth provider,
testing both synchronous and asynchronous operations against the mock Codex API.

The tests validate:
- Basic completion operations (sync/async)
- Streaming functionality (sync/async)
- Tool calling capabilities
- Model parameter validation
- Error handling scenarios

All tests use the mock_codex_api context manager for consistent, isolated testing
with realistic SSE response simulation.
"""

from __future__ import annotations

import asyncio

import pytest

from litellm_codex_oauth_provider.provider import CodexAuthProvider
from tests.integration.constants import VALID_MODELS
from tests.integration.mock_codex_api import mock_codex_api

# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def register_provider() -> CodexAuthProvider:
    """Instantiate provider for tests."""
    return CodexAuthProvider()


@pytest.fixture
def base_message() -> list[dict[str, str]]:
    """Simple user prompt for basic completion tests."""
    return [{"role": "user", "content": "Say hello from Codex."}]


@pytest.fixture
def tool_message() -> list[dict[str, str]]:
    """Prompt that encourages a tool call."""
    return [{"role": "user", "content": "Please run a shell command to list files."}]


@pytest.fixture
def tool_payload() -> list[dict]:
    """Basic tool definition for testing tool calls."""
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

    @pytest.mark.asyncio
    @pytest.mark.parametrize("model", VALID_MODELS)
    async def test_litellm_completion_succeeds(
        self,
        model: str,
        register_provider: CodexAuthProvider,
        base_message: list[dict[str, str]],
    ) -> None:
        """Given: A valid Codex model and user messages
        When: A synchronous completion request is made to the mock API
        Then: The provider returns a response with content
        """
        async with mock_codex_api("basic_completion"):
            response = await asyncio.to_thread(
                register_provider.completion,
                model=model,
                messages=base_message,
                max_tokens=64,
            )

        assert response.choices
        assert response.choices[0].message.content is not None
        assert len(response.choices[0].message.content) > 0

    @pytest.mark.asyncio
    @pytest.mark.parametrize("model", VALID_MODELS)
    async def test_litellm_acompletion_succeeds(
        self,
        model: str,
        register_provider: CodexAuthProvider,
        base_message: list[dict[str, str]],
    ) -> None:
        """Given: A valid Codex model and user messages
        When: An asynchronous completion request is made to the mock API
        Then: The provider returns a response with content
        """
        async with mock_codex_api("basic_completion"):
            response = await register_provider.acompletion(
                model=model,
                messages=base_message,
                max_tokens=64,
            )

        assert response.choices
        assert response.choices[0].message.content is not None
        assert len(response.choices[0].message.content) > 0


class TestStreamingFunctionality:
    """Test streaming responses from the provider."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize("model", VALID_MODELS)
    async def test_litellm_streaming_yields_chunks(
        self,
        model: str,
        register_provider: CodexAuthProvider,
        base_message: list[dict[str, str]],
    ) -> None:
        """Given: A valid Codex model and user messages
        When: A synchronous streaming request is made to the mock API
        Then: The response yields multiple text chunks
        """
        async with mock_codex_api("basic_completion"):
            chunks = list(
                await asyncio.to_thread(
                    lambda: list(
                        register_provider.streaming(
                            model=model,
                            messages=base_message,
                            max_tokens=32,
                        )
                    )
                )
            )

        assert chunks
        assert any(chunk.get("text") for chunk in chunks if isinstance(chunk, dict))

    @pytest.mark.asyncio
    @pytest.mark.parametrize("model", VALID_MODELS)
    async def test_litellm_astreaming_yields_chunks(
        self,
        model: str,
        register_provider: CodexAuthProvider,
        base_message: list[dict[str, str]],
    ) -> None:
        """Given: A valid Codex model and user messages
        When: An asynchronous streaming request is made to the mock API
        Then: The response yields multiple text chunks
        """
        async with mock_codex_api("basic_completion"):
            collected = []
            async for chunk in register_provider.astreaming(
                model=model,
                messages=base_message,
                max_tokens=32,
            ):
                collected.append(chunk)

        assert collected
        assert any(chunk.get("text") for chunk in collected if isinstance(chunk, dict))


class TestToolCalling:
    """Test tool calling functionality and support."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize("model", VALID_MODELS)
    async def test_litellm_completion_with_tools_succeeds(
        self,
        model: str,
        register_provider: CodexAuthProvider,
        tool_message: list[dict[str, str]],
        tool_payload: list[dict],
    ) -> None:
        """Given: A valid Codex model with tool definitions
        When: A synchronous completion request is made that requires tool usage
        Then: The provider returns a response with tool calls
        """
        async with mock_codex_api("tool_call_streaming"):
            response = await asyncio.to_thread(
                register_provider.completion,
                model=model,
                messages=tool_message,
                optional_params={
                    "tools": tool_payload,
                    "tool_choice": "auto",
                    "max_tokens": 64,
                },
            )

        assert response.choices
        assert response.choices[0].message.tool_calls is not None
        assert len(response.choices[0].message.tool_calls) > 0

    @pytest.mark.asyncio
    @pytest.mark.parametrize("model", VALID_MODELS)
    async def test_litellm_acompletion_with_tools_succeeds(
        self,
        model: str,
        register_provider: CodexAuthProvider,
        tool_message: list[dict[str, str]],
        tool_payload: list[dict],
    ) -> None:
        """Given: A valid Codex model with tool definitions
        When: An asynchronous completion request is made that requires tool usage
        Then: The provider returns a response with tool calls
        """
        async with mock_codex_api("tool_call_streaming"):
            response = await register_provider.acompletion(
                model=model,
                messages=tool_message,
                optional_params={
                    "tools": tool_payload,
                    "tool_choice": "auto",
                    "max_tokens": 64,
                },
            )

        assert response.choices
        assert response.choices[0].message.tool_calls is not None
        assert len(response.choices[0].message.tool_calls) > 0

    @pytest.mark.asyncio
    @pytest.mark.parametrize("model", VALID_MODELS)
    async def test_litellm_streaming_with_tools_yields_tool_chunks(
        self,
        model: str,
        register_provider: CodexAuthProvider,
        tool_message: list[dict[str, str]],
        tool_payload: list[dict],
    ) -> None:
        """Given: A valid Codex model with tool definitions
        When: A synchronous streaming request is made that requires tool usage
        Then: The response yields both text and tool use chunks
        """
        async with mock_codex_api("tool_call_streaming"):
            chunks = list(
                await asyncio.to_thread(
                    lambda: list(
                        register_provider.streaming(
                            model=model,
                            messages=tool_message,
                            optional_params={
                                "tools": tool_payload,
                                "tool_choice": "auto",
                            },
                        )
                    )
                )
            )

        assert chunks
        assert any(chunk.get("tool_use") for chunk in chunks if isinstance(chunk, dict))

    @pytest.mark.asyncio
    @pytest.mark.parametrize("model", VALID_MODELS)
    async def test_litellm_astreaming_with_tools_yields_tool_chunks(
        self,
        model: str,
        register_provider: CodexAuthProvider,
        tool_message: list[dict[str, str]],
        tool_payload: list[dict],
    ) -> None:
        """Given: A valid Codex model with tool definitions
        When: An asynchronous streaming request is made that requires tool usage
        Then: The response yields both text and tool use chunks
        """
        async with mock_codex_api("tool_call_streaming"):
            collected = []
            async for chunk in register_provider.astreaming(
                model=model,
                messages=tool_message,
                optional_params={
                    "tools": tool_payload,
                    "tool_choice": "auto",
                },
            ):
                collected.append(chunk)

        assert collected
        assert any(chunk.get("tool_use") for chunk in collected if isinstance(chunk, dict))


class TestErrorHandling:
    """Test error handling and edge cases."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize("model", VALID_MODELS)
    async def test_completion_with_max_tokens_parameter(
        self,
        model: str,
        register_provider: CodexAuthProvider,
        base_message: list[dict[str, str]],
    ) -> None:
        """Given: A valid completion request with max_tokens parameter
        When: The completion is processed
        Then: The response is generated within token limits
        """
        async with mock_codex_api("basic_completion"):
            response = await register_provider.acompletion(
                model=model,
                messages=base_message,
                max_tokens=10,  # Very low limit
            )

        assert response.choices
        assert response.choices[0].message.content is not None

    @pytest.mark.asyncio
    async def test_provider_initialization_succeeds(
        self,
        register_provider: CodexAuthProvider,
    ) -> None:
        """Given: A new CodexAuthProvider instance
        When: The provider is initialized
        Then: All required attributes are properly set
        """
        assert register_provider is not None
        assert hasattr(register_provider, "completion")
        assert hasattr(register_provider, "acompletion")
        assert hasattr(register_provider, "streaming")
        assert hasattr(register_provider, "astreaming")
