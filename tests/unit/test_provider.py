"""Provider unit tests aligned with the simplified CodexAuthProvider.

This module provides comprehensive unit tests for the CodexAuthProvider class,
testing initialization, authentication, completion methods, tool normalization,
and response transformation functionality.

The tests validate:
- Provider initialization and state management
- Bearer token caching and expiry handling
- Completion and streaming method behavior
- Tool definition normalization
- SSE response parsing and transformation
- Model name normalization
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import TYPE_CHECKING, Any

import pytest
from litellm import Choices, Message, ModelResponse

from litellm_codex_oauth_provider import constants
from litellm_codex_oauth_provider.adapter import convert_sse_to_json, transform_response
from litellm_codex_oauth_provider.auth import AuthContext
from litellm_codex_oauth_provider.exceptions import CodexAuthTokenExpiredError
from litellm_codex_oauth_provider.model_map import normalize_model
from litellm_codex_oauth_provider.provider import CodexAuthProvider, _normalize_tools

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from pytest_mock import MockerFixture


# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def provider() -> CodexAuthProvider:
    """Instantiate provider for tests."""
    return CodexAuthProvider()


# =============================================================================
# TESTS
# =============================================================================


def test_provider_init(provider: CodexAuthProvider) -> None:
    """Given a new CodexAuthProvider instance, when initialized, then default state is properly set."""
    assert provider.base_url == f"{constants.CODEX_API_BASE_URL.rstrip('/')}/codex"
    assert provider._cached_token is None  # noqa: SLF001
    assert provider._token_expiry is None  # noqa: SLF001


def test_get_bearer_token_hydrates_cache(
    mocker: MockerFixture, provider: CodexAuthProvider
) -> None:
    """Given a provider with empty cache, when get_bearer_token is called, then auth context is cached for subsequent requests."""
    mocker.patch(
        "litellm_codex_oauth_provider.provider.get_auth_context",
        return_value=AuthContext(access_token="test.token", account_id="acct-1"),
    )
    token = provider.get_bearer_token()
    assert token == "test.token"
    assert provider._cached_token == "test.token"  # noqa: SLF001
    assert provider._account_id == "acct-1"  # noqa: SLF001


def test_get_bearer_token_propagates_expiry(
    provider: CodexAuthProvider, mocker: MockerFixture
) -> None:
    """Given expired token in auth context, when get_bearer_token is called, then expiry error is propagated without refresh attempts."""
    mocker.patch(
        "litellm_codex_oauth_provider.provider.get_auth_context",
        side_effect=CodexAuthTokenExpiredError("expired"),
    )
    with pytest.raises(CodexAuthTokenExpiredError):
        provider.get_bearer_token()


def test_completion_builds_model_response(
    mocker: MockerFixture, provider: CodexAuthProvider
) -> None:
    """Given valid authentication and mocked SSE processing, when completion is called, then ModelResponse is built correctly."""
    mocker.patch(
        "litellm_codex_oauth_provider.provider.get_auth_context",
        return_value=AuthContext(access_token="tok", account_id="acct"),
    )
    mocker.patch(
        "litellm_codex_oauth_provider.provider.fetch_codex_instructions",
        return_value="codex instructions",
    )

    # Capture payload sent to http client
    seen_payload: dict[str, Any] = {}

    async def fake_stream(payload: dict[str, Any]) -> None:  # pragma: no cover - helper
        nonlocal seen_payload
        seen_payload = payload
        if False:
            yield {}  # needed for async generator structure

    provider._http_client.stream_responses_sse = fake_stream  # type: ignore[attr-defined, assignment]  # noqa: SLF001
    mocker.patch(
        "litellm_codex_oauth_provider.provider.CodexAuthProvider._process_sse_events",
        return_value=("hi", [], {"prompt_tokens": 1, "completion_tokens": 1}, "stop"),
    )

    result = provider.completion(
        model="codex/gpt-5.1-codex",
        messages=[{"role": "user", "content": "Hello"}],
        prompt_cache_key="session-123",
    )

    assert isinstance(result, ModelResponse)
    assert result.choices[0].message.content == "hi"


def test_normalize_tools_handles_function_name() -> None:
    """Given tool definitions with function specifications, when normalized, then required fields are filled and valid structure is enforced."""
    tools = _normalize_tools(
        [
            {
                "type": "function",
                "function": {
                    "name": "bash",
                    "description": "Run a bash command",
                    "parameters": {"type": "object"},
                },
            }
        ]
    )
    assert tools is not None
    assert tools[0]["name"] == "bash"
    assert tools[0]["type"] == "function"

    with pytest.raises(ValueError):
        _normalize_tools([{"type": "function", "function": {"description": "missing"}}])


def test_convert_sse_to_json() -> None:
    """Given buffered SSE data containing a completion event, when converted, then final response mapping is extracted."""
    payload = (
        'data: {"type": "response.done", "response": {"id": "1", "choices": '
        '[{"index":0,"message":{"role":"assistant","content":"Hello"}}]}}\n'
        "data: [DONE]"
    )
    parsed = convert_sse_to_json(payload)
    assert parsed["choices"][0]["message"]["content"] == "Hello"


def test_transform_response_with_tool_calls() -> None:
    """Given a response with tool calls, when transformed, then tool call information is preserved in both new and legacy formats."""
    response = {
        "response": {
            "id": "chatcmpl-tool",
            "object": "chat.completion",
            "created": 1_678_000_000,
            "model": "gpt-5.1-codex-max",
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "tool_calls": [
                            {
                                "id": "call_123",
                                "type": "function",
                                "function": {
                                    "name": "get_weather",
                                    "arguments": {"city": "Berlin"},
                                },
                            }
                        ],
                        "function_call": {"name": "get_weather", "arguments": {"city": "Berlin"}},
                    },
                    "finish_reason": "tool_calls",
                }
            ],
            "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
        }
    }
    result = transform_response(response, "gpt-5.1-codex-max")
    assert result.choices[0].message.tool_calls is not None
    assert result.choices[0].message.function_call is not None


def test_streaming_wraps_completion_path(mocker: MockerFixture) -> None:
    """Given a provider with completion mocked, when streaming is called, then it returns an iterator of ModelResponse chunks."""

    def noop(*_args: object, **_kwargs: object) -> None:
        return None

    completion_response = ModelResponse(
        id="123",
        choices=[
            Choices(
                index=0,
                finish_reason="stop",
                message=Message(role="assistant", content="test"),
            )
        ],
        created=0,
        model="model",
        object="chat.completion",
        usage=None,
    )
    provider = CodexAuthProvider()
    mocker.patch.object(provider, "completion", return_value=completion_response)

    async def fake_stream(*_args: object, **_kwargs: object) -> AsyncIterator[ModelResponse]:
        yield completion_response

    mocker.patch(
        "litellm_codex_oauth_provider.provider.CodexAuthProvider.astreaming",
        side_effect=fake_stream,
    )
    logging_obj = SimpleNamespace(
        model_call_details={"litellm_params": {}},
        completion_start_time=None,
        failure_handler=noop,
        success_handler=noop,
        _update_completion_start_time=noop,
    )

    iterator = provider.streaming(model="codex/gpt-5.1-codex", messages=[], logging_obj=logging_obj)
    first_chunk = next(iter(iterator))
    assert hasattr(first_chunk, "choices")


def test_normalize_model_accepts_codex_prefix() -> None:
    """Given a model name that's already in normalized format, when normalized, then the model name is returned unchanged."""
    assert normalize_model("gpt-5-codex-high") == "gpt-5-codex-high"
