"""Model normalization helpers for the Codex OAuth provider."""

from __future__ import annotations

from typing import Final

MODEL_EFFORT_SUFFIXES: Final[tuple[str, ...]] = (
    "none",
    "minimal",
    "low",
    "medium",
    "high",
    "xhigh",
)
BASE_MODELS: Final[tuple[str, ...]] = (
    "gpt-5.1-codex",
    "gpt-5.1-codex-max",
    "gpt-5.1-codex-mini",
    "gpt-5.1",
)


def _build_model_map() -> dict[str, str]:
    """Return a normalization map including legacy aliases."""
    mapping: dict[str, str] = {}

    alias_bases: dict[str, str] = {
        "gpt-5-codex": "gpt-5.1-codex",
        "gpt-5-codex-max": "gpt-5.1-codex-max",
        "gpt-5-codex-mini": "gpt-5.1-codex-mini",
        "gpt-5": "gpt-5.1",
    }

    for base in BASE_MODELS:
        mapping[base] = base
        for suffix in MODEL_EFFORT_SUFFIXES:
            mapping[f"{base}-{suffix}"] = base

    for alias, normalized in alias_bases.items():
        mapping[alias] = normalized
        for suffix in MODEL_EFFORT_SUFFIXES:
            mapping[f"{alias}-{suffix}"] = normalized

    return {key.lower(): value for key, value in mapping.items()}


MODEL_MAP: Final[dict[str, str]] = _build_model_map()


def strip_provider_prefix(model: str) -> str:
    """Remove LiteLLM provider prefixes from a model identifier."""
    return model.replace("codex/", "").replace("codex-", "").strip()


def normalize_model(model: str) -> str:
    """Normalize Codex model identifiers with explicit mapping and fallback rules."""
    cleaned = strip_provider_prefix(model)
    key = cleaned.lower()
    if key in MODEL_MAP:
        return MODEL_MAP[key]

    if "codex-max" in key:
        return "gpt-5.1-codex-max"
    if "codex-mini" in key:
        return "gpt-5.1-codex-mini"
    if "codex" in key:
        return "gpt-5.1-codex"
    if "gpt-5.1" in key:
        return "gpt-5.1"

    return cleaned


def get_model_family(normalized_model: str) -> str:
    """Return the Codex model family label for reasoning constraints."""
    key = normalized_model.lower()
    if "codex-max" in key:
        return "codex-max"
    if "codex-mini" in key:
        return "codex-mini"
    if "codex" in key:
        return "codex"
    if "gpt-5.1" in key:
        return "gpt-5.1"
    return "other"


def extract_reasoning_effort_from_model(model: str) -> str | None:
    """Infer reasoning effort from a model suffix, if present."""
    key = strip_provider_prefix(model).lower()
    for suffix in MODEL_EFFORT_SUFFIXES:
        suffix_token = f"-{suffix}"
        if key.endswith(suffix_token):
            return suffix
    return None
