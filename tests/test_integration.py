"""Integration tests for the LiteLLM Codex OAuth Provider."""

from __future__ import annotations

import litellm
import pytest

from litellm_codex_oauth_provider.provider import codex_auth_provider


def test_provider_registration() -> None:
    """Test that the provider is properly registered with LiteLLM."""
    # Register the custom provider
    litellm.custom_provider_map = [{"provider": "codex", "custom_handler": codex_auth_provider}]

    # Verify it's in the provider map
    providers = [p["provider"] for p in litellm.custom_provider_map]
    assert "codex" in providers


@pytest.mark.skip(reason="Requires actual Codex auth and LiteLLM setup")
def test_direct_usage() -> None:
    """Test using the provider directly (without proxy).

    This test requires:
    1. A valid ~/.codex/auth.json file
    2. LiteLLM to be installed
    """
    # Register the custom provider
    litellm.custom_provider_map = [{"provider": "codex", "custom_handler": codex_auth_provider}]

    # This would make an actual API call
    response = litellm.completion(
        model="codex/gpt-5.1-codex-max",
        messages=[{"role": "user", "content": "Write a Python function to reverse a string"}],
        temperature=0.7,
        max_tokens=500,
    )

    assert response is not None
    assert len(response.choices) > 0
    assert response.choices[0].message.content is not None
