"""Given assorted Codex inputs, when transformation helpers run, then model mapping,

reasoning config, and prompt normalization behave as expected.
"""

from __future__ import annotations

from litellm_codex_oauth_provider.model_map import normalize_model
from litellm_codex_oauth_provider.prompts import _to_codex_input, derive_instructions
from litellm_codex_oauth_provider.reasoning import apply_reasoning_config


def test_normalize_model_handles_alias_and_suffix() -> None:
    """Given a prefixed legacy model, when normalized, then a codex base name is returned.

    Confirms alias resolution drops provider prefixes and effort suffixes to the canonical model.
    """
    normalized = normalize_model("codex/gpt-5.1-codex-high")
    assert normalized == "gpt-5.1-codex-high"


def test_reasoning_config_clamps_codex_mini() -> None:
    """Given a codex-mini xhigh request, when applied, then effort is clamped to high.

    Verifies family-specific constraints prevent unsupported effort levels for mini models.
    """
    config = apply_reasoning_config(
        original_model="gpt-5.1-codex-mini-xhigh",
        normalized_model="gpt-5.1-codex-mini",
        reasoning_effort=None,
        verbosity=None,
    )
    assert config["reasoning"]["effort"] == "high"
    assert config["text"]["verbosity"] == "medium"


def test_reasoning_config_rewrites_minimal_for_codex() -> None:
    """Given a minimal effort codex request, when applied, then effort becomes low.

    Ensures the clamping rules upgrade too-low efforts to the supported floor for codex.
    """
    config = apply_reasoning_config(
        original_model="gpt-5.1-codex-minimal",
        normalized_model="gpt-5.1-codex",
        reasoning_effort=None,
        verbosity="low",
    )
    assert config["reasoning"]["effort"] == "low"
    assert config["text"]["verbosity"] == "low"


def test_derive_instructions_filters_legacy_toolchain_prompts() -> None:
    """Given legacy toolchain prompts, when deriving instructions, then Codex instructions are kept and legacy prompt is removed.

    Validates system prompt filtering strips legacy toolchain markers while preserving provided instructions and user content.
    """
    instructions, filtered_messages = derive_instructions(
        [
            {"role": "system", "content": "toolchain system prompt content"},
            {"role": "user", "content": "Ping"},
        ],
        normalized_model="gpt-5.1-codex",
        instructions_text="codex instructions",
    )

    assert instructions == "codex instructions"
    assert "toolchain system prompt content" not in instructions
    assert filtered_messages == [{"type": "message", "content": "Ping", "role": "user"}]


def test_to_codex_input_user_message() -> None:
    """Given a user message, when converted, then Codex input schema is produced.

    Checks OpenAI user messages map cleanly to Codex message payloads without metadata.
    """
    msg = {"role": "user", "content": "Hello", "id": "abc123"}
    result = _to_codex_input(msg)
    assert result == {"type": "message", "content": "Hello", "role": "user"}


def test_to_codex_input_tool_call() -> None:
    """Given a tool call message, when converted, then function_call schema is emitted.

    Verifies tool_calls payloads are normalized with JSON-string arguments and correct type.
    """
    msg = {"role": "assistant", "tool_calls": [{"name": "foo", "arguments": {"x": 1}}]}
    result = _to_codex_input(msg)

    assert result["type"] == "function_call"
    assert result["function_call"]["name"] == "foo"
    assert '"x": 1' in result["function_call"]["arguments"]


def test_to_codex_input_tool_role_output() -> None:
    """Given a tool role output, when converted, then function_call_output schema is emitted.

    Ensures tool role responses become function_call_output entries with preserved IDs and content.
    """
    msg = {"role": "tool", "tool_call_id": "call-1", "content": {"foo": "bar"}}

    result = _to_codex_input(msg)

    assert result["type"] == "function_call_output"
    assert result["output"]["tool_call_id"] == "call-1"
    assert result["output"]["content"] == {"foo": "bar"}
