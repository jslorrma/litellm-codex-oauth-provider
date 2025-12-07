"""Tests for transformation utilities (model mapping, reasoning, prompts)."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from litellm_codex_oauth_provider.model_map import normalize_model
from litellm_codex_oauth_provider.prompts import TOOL_REMAP_PROMPT, derive_instructions
from litellm_codex_oauth_provider.reasoning import apply_reasoning_config

if TYPE_CHECKING:
    from pytest_mock import MockerFixture


@pytest.fixture(autouse=True)
def mock_codex_instructions(mocker: MockerFixture) -> None:
    """Avoid network fetch during instruction derivation."""
    mocker.patch(
        "litellm_codex_oauth_provider.prompts.get_codex_instructions",
        return_value="codex instructions",
    )


def test_normalize_model_handles_alias_and_suffix() -> None:
    """Given a prefixed legacy model, when normalized, then codex base name is returned."""
    normalized = normalize_model("codex/gpt-5-codex-high")
    assert normalized == "gpt-5.1-codex"


def test_reasoning_config_clamps_codex_mini() -> None:
    """Given a codex-mini xhigh request, when applied, then effort is clamped to high."""
    config = apply_reasoning_config(
        original_model="gpt-5.1-codex-mini-xhigh",
        normalized_model="gpt-5.1-codex-mini",
        reasoning_effort=None,
        verbosity=None,
    )
    assert config["reasoning"]["effort"] == "high"
    assert config["text"]["verbosity"] == "medium"


def test_reasoning_config_rewrites_minimal_for_codex() -> None:
    """Given a minimal effort codex request, when applied, then effort becomes low."""
    config = apply_reasoning_config(
        original_model="gpt-5.1-codex-minimal",
        normalized_model="gpt-5.1-codex",
        reasoning_effort=None,
        verbosity="low",
    )
    assert config["reasoning"]["effort"] == "low"
    assert config["text"]["verbosity"] == "low"


def test_derive_instructions_filters_legacy_toolchain_prompts() -> None:
    """Given legacy toolchain system prompts, when CODEX mode is on, then Codex instructions are used."""
    instructions, filtered_messages = derive_instructions(
        [
            {"role": "system", "content": "toolchain system prompt content"},
            {"role": "user", "content": "Ping"},
        ],
        codex_mode=True,
        normalized_model="gpt-5.1-codex",
    )

    assert instructions == "codex instructions"
    assert "toolchain system prompt content" not in instructions
    assert filtered_messages == [{"type": "message", "content": "Ping", "role": "user"}]


def test_derive_instructions_tool_remap_mode() -> None:
    """Given legacy mode, when deriving instructions, then tool remap guidance is included."""
    instructions, filtered_messages = derive_instructions(
        [{"role": "user", "content": "Ping"}],
        codex_mode=False,
        normalized_model="gpt-5.1-codex",
    )

    assert TOOL_REMAP_PROMPT.splitlines()[0] in instructions
    assert filtered_messages == [{"type": "message", "content": "Ping", "role": "user"}]
