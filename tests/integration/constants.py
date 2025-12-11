"""Shared constants for integration tests."""

from __future__ import annotations

# Valid model names for validation and testing
VALID_MODELS = [
    "gpt-5.1-codex",
    "gpt-5.1",
    "gpt-5.1-codex-max",
    "gpt-5.1-codex-mini",
]

# Valid reasoning effort values
VALID_REASONING_VALUES = ["none", "low", "medium", "high", "xhigh"]

# Reasoning effort to delay mapping for mock responses
REASONING_DELAYS = {"none": 0.02, "low": 0.05, "medium": 0.1, "high": 0.15, "xhigh": 0.2}

# Model-specific instruction patterns
INSTRUCTION_PATTERNS = {
    "gpt-5.1-codex": ["You are a helpful AI coding assistant"],
    "gpt-5.1": ["You are ChatGPT, a large language model"],
    "gpt-5.1-codex-max": ["You are a highly capable coding assistant"],
    "gpt-5.1-codex-mini": ["You are a focused coding assistant"],
}
