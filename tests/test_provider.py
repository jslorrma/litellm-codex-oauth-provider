"""Tests for the provider module."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import TYPE_CHECKING

import pytest
from litellm import Choices, Message, ModelResponse

from litellm_codex_oauth_provider import constants
from litellm_codex_oauth_provider.adapter import convert_sse_to_json, transform_response
from litellm_codex_oauth_provider.auth import AuthContext
from litellm_codex_oauth_provider.exceptions import CodexAuthTokenExpiredError
from litellm_codex_oauth_provider.prompts import TOOL_BRIDGE_PROMPT
from litellm_codex_oauth_provider.provider import CodexAuthProvider

if TYPE_CHECKING:
    from pytest_mock import MockerFixture

PROMPT_TOKENS = 9
COMPLETION_TOKENS = 12
TOTAL_TOKENS = 21


# =============================================================================
# FIXTURES
# =============================================================================
@pytest.fixture
def provider() -> CodexAuthProvider:
    """Create a CodexAuthProvider instance for testing."""
    return CodexAuthProvider()


@pytest.fixture(autouse=True)
def mock_codex_instructions(mocker: MockerFixture) -> None:
    """Prevent network fetch for instructions during tests."""
    for target in (
        "litellm_codex_oauth_provider.remote_resources.fetch_codex_instructions",
        "litellm_codex_oauth_provider.provider.fetch_codex_instructions",
    ):
        mocker.patch(target, return_value="codex instructions")


@pytest.fixture
def mock_openai_response() -> dict:
    """Mock OpenAI API response."""
    return {
        "id": "chatcmpl-123",
        "object": "chat.completion",
        "created": 1677652288,
        "model": "gpt-5.1-codex-max",
        "system_fingerprint": "fp_44709d6fcb",
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": "Hello, world!"},
                "finish_reason": "stop",
            }
        ],
        "usage": {
            "prompt_tokens": PROMPT_TOKENS,
            "completion_tokens": COMPLETION_TOKENS,
            "total_tokens": TOTAL_TOKENS,
        },
    }


# =============================================================================
# TESTS
# =============================================================================
def test_provider_init(provider: CodexAuthProvider) -> None:
    """Given a new provider, when constructed, then base URL and caches are initialized."""
    assert isinstance(provider, CodexAuthProvider)
    assert provider.base_url == f"{constants.CODEX_API_BASE_URL.rstrip('/')}/codex"
    assert provider.cached_token is None
    assert provider.token_expiry is None
    assert provider._codex_mode_enabled is True  # noqa: SLF001


def test_get_bearer_token_cache_miss(mocker: MockerFixture, provider: CodexAuthProvider) -> None:
    """Given no cached token, when get_bearer_token runs, then it fetches and returns a token."""
    mock_get_context = mocker.patch(
        "litellm_codex_oauth_provider.provider.get_auth_context",
        return_value=AuthContext(access_token="test.token", account_id="acct-1"),
    )
    token = provider.get_bearer_token()
    assert token == "test.token"
    assert provider.account_id == "acct-1"
    mock_get_context.assert_called_once()


def test_get_bearer_token_expired_then_refreshed(
    mocker: MockerFixture, provider: CodexAuthProvider
) -> None:
    """Given an expired token, when refresh succeeds, then a new token is returned."""
    # First call raises expired error, second call (after refresh) succeeds
    mocker.patch(
        "litellm_codex_oauth_provider.provider.get_auth_context",
        side_effect=[
            CodexAuthTokenExpiredError("Token expired"),
            AuthContext(access_token="new.token", account_id="acct-2"),
        ],
    )
    mocker.patch(
        "litellm_codex_oauth_provider.provider._refresh_token", return_value="refreshed_token"
    )

    token = provider.get_bearer_token()
    assert token == "new.token"
    assert provider.account_id == "acct-2"


def test_get_bearer_token_expired_refresh_fails(
    mocker: MockerFixture, provider: CodexAuthProvider
) -> None:
    """Given an expired token, when refresh fails, then the original expiry error is raised."""
    mocker.patch(
        "litellm_codex_oauth_provider.provider.get_auth_context",
        side_effect=CodexAuthTokenExpiredError("Token expired"),
    )
    mocker.patch(
        "litellm_codex_oauth_provider.provider._refresh_token",
        side_effect=Exception("Refresh failed"),
    )

    with pytest.raises(CodexAuthTokenExpiredError):
        provider.get_bearer_token()


def test_completion_success(
    mocker: MockerFixture,
    provider: CodexAuthProvider,
    mock_openai_response: dict,
) -> None:
    """Given valid auth and API response, completion returns the expected payload."""
    mocker.patch(
        "litellm_codex_oauth_provider.provider.get_auth_context",
        return_value=AuthContext(access_token="test.token", account_id="acct-1"),
    )
    post_spy = mocker.patch.object(
        provider, "_dispatch_response_request", return_value=mock_openai_response
    )

    result = provider.completion(
        model="codex/gpt-5.1-codex-low",
        messages=[
            {"role": "system", "content": "toolchain system prompt to ignore"},
            {"role": "user", "content": "Hello"},
        ],
        prompt_cache_key="session-123",
    )

    assert isinstance(result, ModelResponse)
    assert result.choices[0].message.content == "Hello, world!"
    payload = post_spy.call_args.kwargs["payload"]
    headers = post_spy.call_args.kwargs["extra_headers"]
    assert payload["model"] == "gpt-5.1-codex"
    assert payload["reasoning"]["effort"] == "low"
    assert payload["store"] is False
    assert payload["include"] == [constants.REASONING_INCLUDE_TARGET]
    assert payload["instructions"] == "codex instructions"
    assert payload["input"] == [{"type": "message", "content": "Hello", "role": "user"}]
    assert headers[constants.SESSION_ID_HEADER] == "session-123"


def test_completion_forwards_supported_kwargs(
    mocker: MockerFixture,
    provider: CodexAuthProvider,
    mock_openai_response: dict,
) -> None:
    """Given optional LiteLLM kwargs, completion forwards supported params."""
    mocker.patch(
        "litellm_codex_oauth_provider.provider.get_auth_context",
        return_value=AuthContext(access_token="test.token", account_id="acct-1"),
    )
    post_spy = mocker.patch.object(
        provider, "_dispatch_response_request", return_value=mock_openai_response
    )

    provider.completion(
        model="codex/gpt-5.1-codex-max",
        messages=[{"role": "user", "content": "Hello"}],
        temperature=0.3,
        max_tokens=77,
        metadata={"source": "unit-test"},
        logging_obj="skip-me",
        reasoning_effort="minimal",
        verbosity="high",
    )

    payload = post_spy.call_args.kwargs["payload"]
    assert "temperature" not in payload  # Codex endpoint rejects temperature
    assert "max_output_tokens" not in payload  # Codex responses rejects this param
    assert payload["metadata"] == {"source": "unit-test"}
    assert "logging_obj" not in payload
    assert "reasoning_effort" not in payload
    assert "verbosity" not in payload


def test_completion_prepends_bridge_when_tools_present(
    mocker: MockerFixture,
    provider: CodexAuthProvider,
    mock_openai_response: dict,
) -> None:
    """Given tools, completion prepends the bridge prompt and forwards tools."""
    mocker.patch(
        "litellm_codex_oauth_provider.provider.get_auth_context",
        return_value=AuthContext(access_token="test.token", account_id="acct-1"),
    )
    post_spy = mocker.patch.object(
        provider, "_dispatch_response_request", return_value=mock_openai_response
    )
    tools = [
        {
            "type": "function",
            "function": {
                "name": "bash",
                "description": "Run a bash command",
                "parameters": {"type": "object", "properties": {"command": {"type": "string"}}},
            },
        }
    ]

    provider.completion(
        model="codex/gpt-5.1-codex-max",
        messages=[{"role": "user", "content": "Please request a tool call to read HOME."}],
        tools=tools,
        tool_choice="auto",
        parallel_tool_calls=False,
    )

    payload = post_spy.call_args.kwargs["payload"]
    normalized_tool = payload["tools"][0]
    assert normalized_tool["name"] == "bash"
    assert normalized_tool["description"] == "Run a bash command"
    assert normalized_tool["type"] == "function"
    assert normalized_tool["parameters"]["properties"]["command"]["type"] == "string"
    assert payload["tool_choice"] == "auto"
    assert payload["parallel_tool_calls"] is False
    input_messages = payload["input"]
    assert input_messages[0]["role"] == "developer"
    assert input_messages[0]["content"][0]["text"].startswith("# Codex Tool Bridge")
    assert TOOL_BRIDGE_PROMPT in input_messages[0]["content"][0]["text"]
    assert input_messages[1]["role"] == "user"


def test_completion_raises_on_missing_tool_name(provider: CodexAuthProvider) -> None:
    """Given a tool without function name, when building payload, then a clear error is raised."""
    with pytest.raises(ValueError, match=r"function\.name"):
        provider._normalize_tools(  # noqa: SLF001
            [{"type": "function", "function": {"description": "missing name"}}]
        )


def test_tool_normalization_strips_type(provider: CodexAuthProvider) -> None:
    """Given a tool with an explicit type, when normalized, then type is removed for Codex."""
    tools = provider._normalize_tools(  # noqa: SLF001
        [
            {
                "type": "function",
                "name": "bash",
                "description": "Run a bash command",
                "parameters": {"type": "object"},
            }
        ]
    )
    assert tools[0]["type"] == "function"
    assert tools[0]["name"] == "bash"


def test_completion_does_not_add_bridge_without_tools(
    mocker: MockerFixture,
    provider: CodexAuthProvider,
    mock_openai_response: dict,
) -> None:
    """Given no tools, when completion runs, then bridge prompt is omitted."""
    mocker.patch(
        "litellm_codex_oauth_provider.provider.get_auth_context",
        return_value=AuthContext(access_token="test.token", account_id="acct-1"),
    )
    post_spy = mocker.patch.object(
        provider, "_dispatch_response_request", return_value=mock_openai_response
    )

    provider.completion(
        model="codex/gpt-5.1-codex-max", messages=[{"role": "user", "content": "Hello"}]
    )

    payload = post_spy.call_args.kwargs["payload"]
    input_messages = payload["input"]
    assert input_messages[0]["role"] == "user"
    assert not any(msg.get("role") == "developer" for msg in input_messages)


def test_completion_http_error(mocker: MockerFixture, provider: CodexAuthProvider) -> None:
    """Given an HTTP failure, when completion is called, then a RuntimeError is raised."""
    mocker.patch(
        "litellm_codex_oauth_provider.provider.get_auth_context",
        return_value=AuthContext(access_token="test.token", account_id="acct-1"),
    )
    mocker.patch.object(
        provider,
        "_dispatch_response_request",
        side_effect=RuntimeError("Codex API error 401"),
    )

    with pytest.raises(RuntimeError, match="Codex API error 401"):
        provider.completion(
            model="codex/gpt-5.1-codex-max", messages=[{"role": "user", "content": "Hello"}]
        )


def test_acompletion_success(
    mocker: MockerFixture,
    provider: CodexAuthProvider,
    mock_openai_response: dict,
) -> None:
    """Given valid auth and API response, awaiting acompletion yields a ModelResponse."""
    mocker.patch(
        "litellm_codex_oauth_provider.provider.get_auth_context",
        return_value=AuthContext(access_token="test.token", account_id="acct-1"),
    )
    mocker.patch.object(
        provider, "_dispatch_response_request_async", return_value=mock_openai_response
    )

    result = asyncio.run(
        provider.acompletion(
            model="codex/gpt-5.1-codex-max", messages=[{"role": "user", "content": "Hello"}]
        )
    )

    assert isinstance(result, ModelResponse)
    assert result.choices[0].message.content == "Hello, world!"


def test_convert_sse_to_json() -> None:
    """Given buffered SSE data, when converted, then the response payload is extracted."""
    payload = (
        'data: {"type": "response.done", "response": {"id": "1", "choices": '
        '[{"index":0,"message":{"role":"assistant","content":"Hello"}}]}}\n'
        "data: [DONE]"
    )

    parsed = convert_sse_to_json(payload)

    assert parsed["choices"][0]["message"]["content"] == "Hello"


def test_transform_response(mock_openai_response: dict) -> None:
    """Given an OpenAI-style response, transform_response mirrors input values."""
    result = transform_response(mock_openai_response, "gpt-5.1-codex-max")

    assert isinstance(result, ModelResponse)
    assert result.id == "chatcmpl-123"
    assert result.model == "gpt-5.1-codex-max"
    assert result.choices[0].message.content == "Hello, world!"
    assert result.usage.prompt_tokens == PROMPT_TOKENS
    assert result.usage.completion_tokens == COMPLETION_TOKENS
    assert result.usage.total_tokens == TOTAL_TOKENS


def test_transform_response_with_tool_calls() -> None:
    """Given a tool-calling response, transform_response preserves tool calls."""
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
            "usage": {
                "prompt_tokens": PROMPT_TOKENS,
                "completion_tokens": COMPLETION_TOKENS,
                "total_tokens": TOTAL_TOKENS,
            },
        }
    }

    result = transform_response(response, "gpt-5.1-codex-max")

    assert result.choices[0].finish_reason == "tool_calls"
    message = result.choices[0].message
    assert message.tool_calls is not None
    assert message.tool_calls[0].function.name == "get_weather"
    assert message.tool_calls[0].function.arguments == '{"city": "Berlin"}'
    assert message.function_call is not None
    assert message.function_call.name == "get_weather"
    assert message.function_call.arguments == '{"city": "Berlin"}'
    assert message.content is None


def test_transform_response_with_top_level_tool_calls() -> None:
    """Given Codex-style tool calls (name/arguments at top level), then tool calls are parsed."""
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
                                "name": "bash",
                                "arguments": '{"command":"echo hi"}',
                            }
                        ],
                    },
                    "finish_reason": "tool_calls",
                }
            ],
            "usage": {
                "prompt_tokens": PROMPT_TOKENS,
                "completion_tokens": COMPLETION_TOKENS,
                "total_tokens": TOTAL_TOKENS,
            },
        }
    }

    result = transform_response(response, "gpt-5.1-codex-max")

    message = result.choices[0].message
    assert message.tool_calls is not None
    assert message.tool_calls[0].function.name == "bash"
    assert message.tool_calls[0].function.arguments == '{"command":"echo hi"}'
    assert message.content is None


def test_transform_response_falls_back_to_output() -> None:
    """Given empty content but output field, transform_response derives content from output."""
    response = {
        "response": {
            "id": "chatcmpl-output",
            "object": "chat.completion",
            "created": 1_678_000_000,
            "model": "gpt-5.1-codex-max",
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": ""},
                    "finish_reason": "stop",
                }
            ],
            "usage": {
                "prompt_tokens": PROMPT_TOKENS,
                "completion_tokens": COMPLETION_TOKENS,
                "total_tokens": TOTAL_TOKENS,
            },
            "output": [{"text": "Hello from output"}],
        }
    }

    result = transform_response(response, "gpt-5.1-codex-max")

    assert result.choices[0].message.content == "Hello from output"


def test_transform_response_with_function_call_output() -> None:
    """Given function_call output items, transform_response emits tool_calls."""
    response = {
        "response": {
            "id": "chatcmpl-fc",
            "object": "chat.completion",
            "created": 1_678_000_000,
            "model": "gpt-5.1-codex-max",
            "output": [
                {
                    "id": "fc_123",
                    "type": "function_call",
                    "status": "completed",
                    "arguments": '{"command":"echo $HOME"}',
                    "call_id": "call_1",
                    "name": "bash",
                }
            ],
            "usage": {
                "prompt_tokens": PROMPT_TOKENS,
                "completion_tokens": COMPLETION_TOKENS,
                "total_tokens": TOTAL_TOKENS,
            },
        }
    }

    result = transform_response(response, "gpt-5.1-codex-max")

    message = result.choices[0].message
    assert message.tool_calls is not None
    assert message.tool_calls[0].function.name == "bash"
    assert message.tool_calls[0].function.arguments == '{"command":"echo $HOME"}'
    assert message.content is None
    assert result.choices[0].finish_reason == "tool_calls"


def test_streaming_wraps_completion(mocker: MockerFixture, provider: CodexAuthProvider) -> None:
    """Given streaming call, completion result is wrapped in CustomStreamWrapper."""

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
    mocker.patch.object(provider, "completion", return_value=completion_response)
    logging_obj = SimpleNamespace(
        model_call_details={"litellm_params": {}},
        completion_start_time=None,
        failure_handler=noop,
        success_handler=noop,
        _update_completion_start_time=noop,
    )

    wrapper = provider.streaming(model="codex/gpt-5.1-codex", messages=[], logging_obj=logging_obj)

    first_chunk = next(iter(wrapper))
    assert hasattr(first_chunk, "choices")
