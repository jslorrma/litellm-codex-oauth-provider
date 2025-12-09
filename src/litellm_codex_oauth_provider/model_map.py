"""Simplified model normalization helpers for the Codex OAuth provider.

This module provides streamlined model name normalization and alias resolution
for Codex models. It focuses on core functionality while maintaining compatibility
with the most common model formats.

The simplified mapping system supports:
- Basic provider prefix stripping (codex/, codex-oauth/, codex-)
- Simple model name normalization
- Basic instruction prompt mapping
- Clear, maintainable code structure

Supported Model Formats
-----------------------
- **Standard**: `gpt-5.1-codex`, `gpt-5.1-codex-max`, `gpt-5.1-codex-mini`
- **Provider Prefixed**: `codex/gpt-5.1-codex`, `codex-oauth/gpt-5.1-codex-max`
- **Legacy**: `gpt-5-codex`, `gpt-5-codex-max` (auto-upgraded)

Model Mapping Rules
-------------------
1. **Prefix Stripping**: Remove LiteLLM provider prefixes
2. **Version Normalization**: Auto-upgrade gpt-5 to gpt-5.1
3. **Suffix Normalization**: Keep -max, -mini suffixes as-is
4. **Fallback**: Return normalized model as-is if not recognized

Examples
--------
Basic model normalization:

>>> from litellm_codex_oauth_provider.model_map import normalize_model
>>> normalize_model("codex/gpt-5.1-codex-max")
'gpt-5.1-codex-max'

>>> normalize_model("gpt-5-codex-mini")
'gpt-5.1-codex-mini'

Prefix stripping:

>>> from litellm_codex_oauth_provider.model_map import _strip_provider_prefix
>>> _strip_provider_prefix("codex/gpt-5.1-codex")
'gpt-5.1-codex'

>>> _strip_provider_prefix("codex-oauth/gpt-5.1-codex-max")
'gpt-5.1-codex-max'
"""

from __future__ import annotations

from typing import Final

# Reasoning effort suffixes
MODEL_EFFORT_SUFFIXES: Final[tuple[str, ...]] = (
    "none",
    "minimal",
    "low",
    "medium",
    "high",
    "xhigh",
)

# Model mappings for common Codex models
MODEL_MAPPINGS: Final[dict[str, str]] = {
    # Legacy model upgrades
    "gpt-5-codex": "gpt-5.1-codex",
    "gpt-5-codex-max": "gpt-5.1-codex-max",
    "gpt-5-codex-mini": "gpt-5.1-codex-mini",
    # Supported models (these pass through unchanged)
    "gpt-5.1-codex": "gpt-5.1-codex",
    "gpt-5.1-codex-max": "gpt-5.1-codex-max",
    "gpt-5.1-codex-mini": "gpt-5.1-codex-mini",
    "gpt-5.1": "gpt-5.1",
    "gpt-5": "gpt-5.1",
}

# Provider prefixes to strip (longer prefixes first to avoid partial matches)
PROVIDER_PREFIXES: Final[list[str]] = [
    "codex-oauth/",
    "codex_oauth/",
    "codex/",
    "codex-",
]


def _strip_provider_prefix(model: str) -> str:
    """Strip provider prefixes from model string.

    Parameters
    ----------
    model : str
        Model string potentially containing provider prefixes

    Returns
    -------
    str
        Model string with provider prefixes removed

    Examples
    --------
    >>> _strip_provider_prefix("codex/gpt-5.1-codex")
    'gpt-5.1-codex'
    >>> _strip_provider_prefix("codex-oauth/gpt-5.1-codex-max")
    'gpt-5.1-codex-max'
    >>> _strip_provider_prefix("gpt-5.1-codex")
    'gpt-5.1-codex'
    """
    stripped = model.lower()
    for prefix in PROVIDER_PREFIXES:
        if stripped.startswith(prefix):
            return stripped[len(prefix) :]
    return stripped


def normalize_model(model: str) -> str:
    """Normalize model name for Codex API compatibility.

    This function provides streamlined model normalization:
    1. Strip provider prefixes
    2. Apply basic model mappings
    3. Return normalized model name

    Parameters
    ----------
    model : str
        Input model string (may include provider prefixes)

    Returns
    -------
    str
        Normalized model name for Codex API

    Examples
    --------
    >>> normalize_model("codex/gpt-5.1-codex")
    'gpt-5.1-codex'
    >>> normalize_model("gpt-5-codex-mini")
    'gpt-5.1-codex-mini'
    >>> normalize_model("codex-oauth/gpt-5.1-codex-max")
    'gpt-5.1-codex-max'
    >>> normalize_model("gpt-5.1-codex")
    'gpt-5.1-codex'

    Notes
    -----
    - Unknown models are returned as-is after prefix stripping
    - Version auto-upgrade (gpt-5 → gpt-5.1) for legacy compatibility
    - Case-insensitive processing
    """
    # Strip provider prefixes and normalize case
    normalized = _strip_provider_prefix(model).lower()

    # Apply known mappings
    if normalized in MODEL_MAPPINGS:
        return MODEL_MAPPINGS[normalized]

    # Fallback: return normalized model as-is
    return normalized


def get_model_family(normalized_model: str) -> str:
    """Get model family classification for reasoning constraints.

    Parameters
    ----------
    normalized_model : str
        Canonical Codex model identifier.

    Returns
    -------
    str
        Family label (e.g., "codex", "codex-max", "codex-mini", "gpt-5.1", "other").

    Examples
    --------
    >>> get_model_family("gpt-5.1-codex-max")
    'codex-max'
    >>> get_model_family("gpt-5.1-codex")
    'codex'
    >>> get_model_family("gpt-5.1-codex-mini")
    'codex-mini'
    >>> get_model_family("gpt-5.1")
    'gpt-5.1'
    >>> get_model_family("unknown-model")
    'other'
    """
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
    """Extract reasoning effort from model suffix, if present.

    Parameters
    ----------
    model : str
        Model identifier that may include an effort suffix.

    Returns
    -------
    str | None
        Effort level when detected, otherwise None.

    Examples
    --------
    >>> extract_reasoning_effort_from_model("gpt-5.1-codex-high")
    'high'
    >>> extract_reasoning_effort_from_model("gpt-5.1-codex")
    >>> extract_reasoning_effort_from_model("codex/gpt-5.1-codex-medium")
    'medium'
    """
    key = _strip_provider_prefix(model).lower()
    for suffix in MODEL_EFFORT_SUFFIXES:
        suffix_token = f"-{suffix}"
        if key.endswith(suffix_token):
            return suffix
    return None


# Legacy function names for backward compatibility
def _strip_provider_prefix_legacy(model: str) -> str:
    """Legacy function name for backward compatibility."""
    return _strip_provider_prefix(model)
