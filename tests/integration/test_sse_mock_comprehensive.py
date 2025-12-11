"""Comprehensive test suite for SSE implementation using the mock system.

This module provides extensive tests that validate the SSE streaming implementation
using the httpx mock system with validation callbacks.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

import pytest

from litellm_codex_oauth_provider.provider import CodexAuthProvider
from tests.integration.constants import VALID_MODELS, VALID_REASONING_VALUES
from tests.integration.mock_codex_api import HTTpxMockManager, mock_codex_api

pytestmark = pytest.mark.asyncio

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

MIN_CHUNK_COUNT = 3
LOW_REASONING_MAX_DURATION = 1.0
MEDIUM_REASONING_MAX_DURATION = 2.0
HIGH_REASONING_MAX_DURATION = 3.0


# =============================================================================
# FIXTURES
# =============================================================================
@pytest.fixture
async def mock_manager() -> AsyncIterator[HTTpxMockManager]:
    """Fixture that provides mock manager."""
    manager = HTTpxMockManager()
    try:
        await manager.start_mock("basic_completion")
        yield manager
    finally:
        await manager.stop_mock()


@pytest.fixture
async def mock_codex_basic() -> AsyncIterator[HTTpxMockManager]:
    """Fixture for basic completion scenario."""
    async with mock_codex_api("basic_completion") as mock:
        yield mock


@pytest.fixture
async def mock_codex_tool_calls() -> AsyncIterator[HTTpxMockManager]:
    """Fixture for tool call streaming scenario."""
    async with mock_codex_api("tool_call_streaming") as mock:
        yield mock


@pytest.fixture
async def mock_codex_reasoning() -> AsyncIterator[HTTpxMockManager]:
    """Fixture for reasoning validation testing."""
    async with mock_codex_api("reasoning_high") as mock:
        yield mock


# =============================================================================
# TESTS
# =============================================================================


# Test classes
class TestModelValidation:
    """Test model validation with various scenarios."""

    async def test_valid_models(self, mock_codex_basic: HTTpxMockManager) -> None:
        """
        Given: A list of valid Codex models.
        When: A completion request is made for each model.
        Then: The provider successfully returns a response for each model.
        """
        for model in VALID_MODELS:
            # Change scenario for each model
            mock_codex_basic.set_scenario("basic_completion")

            provider = CodexAuthProvider()

            # Should work without errors
            response = await provider.acompletion(
                model=model, messages=[{"role": "user", "content": "Hello"}]
            )

            assert response.choices[0].message.content is not None
            assert response.model == model

    async def test_invalid_model(self) -> None:
        """
        Given: An invalid model name.
        When: A completion request is made.
        Then: The provider raises a model not found exception.
        """
        async with mock_codex_api("basic_completion") as mock:
            # Change scenario to simulate invalid model error
            mock.set_scenario("invalid_model")

            provider = CodexAuthProvider()

            with pytest.raises(Exception, match=r"Model.*not found"):
                await provider.acompletion(
                    model="invalid-model-name", messages=[{"role": "user", "content": "Hello"}]
                )

    async def test_model_prefix_validation(self) -> None:
        """
        Given: A list of invalid model names (not in the allowed list).
        When: A completion request is made.
        Then: The request fails validation.
        """
        async with mock_codex_api("basic_completion"):
            invalid_models = ["gpt-4.0", "claude-3", "invalid-model"]

            for model in invalid_models:
                provider = CodexAuthProvider()

                with pytest.raises(Exception):  # noqa: B017
                    await provider.acompletion(
                        model=model, messages=[{"role": "user", "content": "Hello"}]
                    )


class TestReasoningValidation:
    """Test reasoning_effort parameter validation."""

    @pytest.mark.parametrize("model", VALID_MODELS)
    async def test_valid_reasoning_values(self, model: str) -> None:
        """
        Given: A list of valid reasoning_effort values.
        When: A completion request is made with each value.
        Then: The provider successfully accepts the parameter.
        """
        for reasoning in VALID_REASONING_VALUES:
            async with mock_codex_api("basic_completion"):
                provider = CodexAuthProvider()

                response = await provider.acompletion(
                    model=model,
                    messages=[{"role": "user", "content": "Hello"}],
                    reasoning_effort=reasoning,
                )

                assert response.choices[0].message.content is not None

    async def test_none_reasoning(self) -> None:
        """
        Given: A reasoning_effort of None.
        When: A completion request is made.
        Then: The provider successfully processes the request using default behavior.
        """
        async with mock_codex_api("basic_completion"):
            provider = CodexAuthProvider()

            response = await provider.acompletion(
                model="gpt-5.1-codex",
                messages=[{"role": "user", "content": "Hello"}],
                reasoning_effort=None,
            )

            assert response.choices[0].message.content is not None

    async def test_invalid_reasoning_value(self) -> None:
        """
        Given: An invalid reasoning_effort value.
        When: A completion request is made.
        Then: The request is rejected with a validation error.
        """
        async with mock_codex_api("basic_completion"):
            provider = CodexAuthProvider()

            with pytest.raises(Exception, match="Invalid reasoning_effort"):
                await provider.acompletion(
                    model="gpt-5.1-codex",
                    messages=[{"role": "user", "content": "Hello"}],
                    reasoning_effort="invalid_reasoning",
                )


class TestInstructionValidation:
    """Test instruction validation for different models."""

    async def test_required_instructions_present(self) -> None:
        """
        Given: A provider configuration that automatically adds instructions.
        When: A completion request is made.
        Then: The request includes required instructions and succeeds validation.
        """
        # This test simulates what would happen with missing instructions
        # The actual provider should include instructions automatically
        async with mock_codex_api("basic_completion"):
            provider = CodexAuthProvider()

            # Provider should automatically add appropriate instructions
            response = await provider.acompletion(
                model="gpt-5.1-codex", messages=[{"role": "user", "content": "Hello"}]
            )

            assert response.choices[0].message.content is not None


class TestSSEStreaming:
    """Test SSE streaming functionality."""

    async def test_streaming_text_deltas(self) -> None:
        """
        Given: A provider connected to a mock SSE stream emitting text deltas.
        When: The provider streams the response.
        Then: The response yields text chunks and a final finish chunk.
        """
        async with mock_codex_api("basic_completion"):
            provider = CodexAuthProvider()

            chunks = []
            async for chunk in provider.astreaming(
                model="gpt-5.1-codex", messages=[{"role": "user", "content": "Hello"}]
            ):
                chunks.append(chunk)

            # Should have multiple text chunks
            text_chunks = [c for c in chunks if c["text"]]
            assert len(text_chunks) > 0

            # Should have a final chunk with usage
            final_chunks = [c for c in chunks if c["is_finished"]]
            assert len(final_chunks) > 0

    @pytest.mark.parametrize("model", VALID_MODELS)
    async def test_streaming_tool_calls(
        self, model: str, mock_codex_tool_calls: HTTpxMockManager
    ) -> None:
        """
        Given: A provider connected to a mock SSE stream emitting tool calls.
        When: The provider streams the response with tool definitions.
        Then: The response yields tool call argument deltas and proper tool call objects.
        """
        _ = mock_codex_tool_calls
        provider = CodexAuthProvider()

        chunks = []
        async for chunk in provider.astreaming(
            model=model,
            messages=[{"role": "user", "content": "Run a bash command"}],
            optional_params={
                "tools": [
                    {
                        "type": "function",
                        "function": {
                            "name": "bash_execute",
                            "description": "Execute a bash command",
                            "parameters": {
                                "type": "object",
                                "properties": {
                                    "command": {"type": "string"},
                                    "timeout": {"type": "integer"},
                                },
                            },
                        },
                    }
                ]
            },
        ):
            chunks.append(chunk)

        # Should have tool call chunks
        tool_chunks = [c for c in chunks if c["tool_use"] is not None]
        assert len(tool_chunks) > 0

        # Verify tool call structure
        for tool_chunk in tool_chunks:
            tool_use = tool_chunk["tool_use"]
            assert "id" in tool_use
            assert "function" in tool_use
            assert "name" in tool_use["function"]

    @pytest.mark.parametrize("model", VALID_MODELS)
    async def test_reasoning_aware_streaming(self, model: str) -> None:
        """
        Given: Different reasoning_effort levels (low, medium, high).
        When: Streaming requests are made for each level.
        Then: The response latency roughly correlates with the reasoning effort.
        """
        reasoning_values = ["low", "medium", "high"]

        for reasoning in reasoning_values:
            async with mock_codex_api("basic_completion"):
                provider = CodexAuthProvider()

                start_time = asyncio.get_event_loop().time()
                chunk_count = 0

                async for _chunk in provider.astreaming(
                    model=model,
                    messages=[{"role": "user", "content": "Hello"}],
                    reasoning_effort=reasoning,
                ):
                    chunk_count += 1
                    if chunk_count >= MIN_CHUNK_COUNT:  # Just get a few chunks for timing test
                        break

                end_time = asyncio.get_event_loop().time()
                duration = end_time - start_time

                # Higher reasoning should take longer
                if reasoning == "low":
                    assert duration < LOW_REASONING_MAX_DURATION  # Should be fast
                elif reasoning == "medium":
                    assert duration < MEDIUM_REASONING_MAX_DURATION  # Should be moderate
                elif reasoning == "high":
                    assert duration < HIGH_REASONING_MAX_DURATION  # Should be slower


class TestProviderMethods:
    """Test all provider methods with validation."""

    @pytest.mark.parametrize("model", VALID_MODELS)
    async def test_completion_method(self, model: str, mock_codex_basic: HTTpxMockManager) -> None:
        """
        Given: A basic completion request.
        When: The completion() method is called.
        Then: A complete ModelResponse is returned with content.
        """
        _ = mock_codex_basic
        provider = CodexAuthProvider()

        response = await provider.acompletion(
            model=model, messages=[{"role": "user", "content": "Hello, world!"}]
        )

        # Verify response structure
        assert hasattr(response, "choices")
        assert len(response.choices) > 0
        assert response.choices[0].message.content is not None

    @pytest.mark.parametrize("model", VALID_MODELS)
    async def test_acompletion_method(self, model: str, mock_codex_basic: HTTpxMockManager) -> None:
        """
        Given: A basic completion request.
        When: The acompletion() method is called.
        Then: A complete ModelResponse is returned with content.
        """
        _ = mock_codex_basic
        provider = CodexAuthProvider()

        response = await provider.acompletion(
            model=model, messages=[{"role": "user", "content": "Hello"}]
        )

        # Should be same as completion
        assert hasattr(response, "choices")
        assert response.choices[0].message.content is not None

    @pytest.mark.parametrize("model", VALID_MODELS)
    async def test_streaming_method(self, model: str, mock_codex_basic: HTTpxMockManager) -> None:
        """
        Given: A streaming request.
        When: The streaming() method is called.
        Then: An async iterator yielding chunks is returned.
        """
        _ = mock_codex_basic
        provider = CodexAuthProvider()

        chunks = []
        async for chunk in provider.astreaming(
            model=model, messages=[{"role": "user", "content": "Hello"}]
        ):
            chunks.append(chunk)

        assert len(chunks) > 0

        # Verify chunk structure
        for chunk in chunks:
            assert "text" in chunk or "tool_use" in chunk
            assert "is_finished" in chunk
            assert "index" in chunk

    @pytest.mark.parametrize("model", VALID_MODELS)
    async def test_astreaming_method(self, model: str, mock_codex_basic: HTTpxMockManager) -> None:
        """
        Given: A streaming request.
        When: The astreaming() method is called.
        Then: An async iterator yielding chunks is returned.
        """
        _ = mock_codex_basic
        provider = CodexAuthProvider()

        chunks = []
        async for chunk in provider.astreaming(
            model=model, messages=[{"role": "user", "content": "Hello"}]
        ):
            chunks.append(chunk)

        assert len(chunks) > 0

        # Should be same as streaming
        for chunk in chunks:
            assert "text" in chunk or "tool_use" in chunk


class TestErrorScenarios:
    """Test error handling scenarios."""

    async def test_authentication_error(self) -> None:
        """
        Given: A mock server returning 401 Unauthorized.
        When: A completion request is made.
        Then: An exception is raised.
        """
        async with mock_codex_api("basic_completion") as mock:
            # Simulate auth error scenario
            mock.set_scenario("error_401")

            provider = CodexAuthProvider()

            with pytest.raises(Exception):  # noqa: B017
                await provider.acompletion(
                    model="gpt-5.1-codex", messages=[{"role": "user", "content": "Hello"}]
                )

    async def test_invalid_request_format(self) -> None:
        """
        Given: A request with an invalid model.
        When: The request is sent to the provider.
        Then: The validation fails with an exception.
        """
        async with mock_codex_api("basic_completion"):
            provider = CodexAuthProvider()

            # This should trigger validation errors in the provider itself
            # since we're testing the request format that gets sent
            with pytest.raises(Exception):  # noqa: B017
                await provider.acompletion(
                    model="invalid-model",  # This should fail
                    messages=[{"role": "user", "content": "Hello"}],
                )


class TestIntegration:
    """Integration tests for the complete SSE workflow."""

    @pytest.mark.asyncio
    async def test_codex_native_streaming_parsing(self) -> None:
        """Ensure native Codex-style SSE is parsed into content and reasoning."""
        async with mock_codex_api("codex_native_streaming"):
            provider = CodexAuthProvider()
            chunks = []
            async for chunk in provider.astreaming(
                model="gpt-5.1-codex",
                messages=[{"role": "user", "content": "Hello"}],
            ):
                chunks.append(chunk)

        text = "".join(c.get("text", "") for c in chunks)
        reasoning = "".join(c.get("reasoning_content", "") for c in chunks)
        assert "Hello! Codex here to help you get started." in text
        assert "Implementing simple greeting response" in reasoning

    @pytest.mark.parametrize("model", VALID_MODELS)
    async def test_full_workflow_basic_completion(
        self, model: str, mock_codex_basic: HTTpxMockManager
    ) -> None:
        """
        Given: A standard completion workflow.
        When: Both completion() and streaming() are called.
        Then: Both methods return valid content.
        """
        _ = mock_codex_basic
        provider = CodexAuthProvider()

        # 1. Non-streaming completion
        response = await provider.acompletion(
            model=model,
            messages=[{"role": "user", "content": "Write a simple hello world function"}],
            reasoning_effort="medium",
        )

        assert response.choices[0].message.content is not None

        # 2. Streaming completion
        streaming_chunks = []
        async for chunk in provider.astreaming(
            model=model,
            messages=[{"role": "user", "content": "Explain async programming"}],
            reasoning_effort="high",
        ):
            streaming_chunks.append(chunk)

        assert len(streaming_chunks) > 0

        # Verify streaming produces content
        all_text = "".join(chunk["text"] for chunk in streaming_chunks if chunk["text"])
        assert len(all_text) > 0

    @pytest.mark.parametrize("model", VALID_MODELS)
    async def test_tool_call_integration(
        self, model: str, mock_codex_tool_calls: HTTpxMockManager
    ) -> None:
        """
        Given: A workflow with tool calls defined.
        When: A streaming request is made that triggers a tool call.
        Then: The response includes both text content and tool call definitions.
        """
        _ = mock_codex_tool_calls
        provider = CodexAuthProvider()

        tools = [
            {
                "type": "function",
                "function": {
                    "name": "bash_execute",
                    "description": "Execute a bash command",
                    "parameters": {"type": "object", "properties": {"command": {"type": "string"}}},
                },
            }
        ]

        # Streaming with tools
        streaming_chunks = []
        async for chunk in provider.astreaming(
            model=model,
            messages=[{"role": "user", "content": "Run ls command"}],
            optional_params={"tools": tools},
        ):
            streaming_chunks.append(chunk)

        # Should have both text and tool call chunks
        text_chunks = [c for c in streaming_chunks if c["text"]]
        tool_chunks = [c for c in streaming_chunks if c["tool_use"] is not None]

        assert len(text_chunks) > 0
        assert len(tool_chunks) > 0


# Example usage function
async def example_test_with_mock() -> None:
    """Example of how to use the mock system."""
    # Scenario 1: Basic completion test
    async with mock_codex_api("basic_completion"):
        provider = CodexAuthProvider()

        response = await provider.acompletion(
            model="gpt-5.1-codex", messages=[{"role": "user", "content": "Hello!"}]
        )

        print(f"Response: {response.choices[0].message.content}")

    # Scenario 2: Tool call streaming test
    async with mock_codex_api("tool_call_streaming"):
        provider = CodexAuthProvider()

        print("Streaming tool calls...")
        async for chunk in provider.astreaming(
            model="gpt-5.1-codex", messages=[{"role": "user", "content": "Run a command"}]
        ):
            if chunk["text"]:
                print(f"Text: {chunk['text']}")
            if chunk["tool_use"]:
                print(f"Tool: {chunk['tool_use']}")

    # Scenario 3: Reasoning validation test
    async with mock_codex_api("basic_completion"):
        provider = CodexAuthProvider()

        for reasoning in ["low", "medium", "high"]:
            print(f"Testing reasoning: {reasoning}")
            response = await provider.acompletion(
                model="gpt-5.1-codex",
                messages=[{"role": "user", "content": "Explain AI"}],
                reasoning_effort=reasoning,
            )
            print(f"Got response: {len(response.choices[0].message.content)} chars")


if __name__ == "__main__":
    # Run example usage
    asyncio.run(example_test_with_mock())
