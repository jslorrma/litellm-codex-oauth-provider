"""Model normalization helpers for the Codex OAuth provider.

This module provides intelligent model name normalization and alias resolution for
Codex models. It handles the conversion of various LiteLLM model string formats
into Codex-compatible identifiers.

The mapping system supports:
- Provider prefix stripping (codex/, codex-oauth/, codex-)
- Model alias resolution and normalization
- Effort level suffix handling (none, minimal, low, medium, high, xhigh)
- Legacy model name compatibility
- Model family classification for reasoning constraints

Model Normalization Process
---------------------------
1. **Prefix Stripping**: Remove LiteLLM provider prefixes
2. **Case Normalization**: Convert to lowercase for lookup
3. **Alias Resolution**: Map to canonical model names
4. **Effort Extraction**: Parse reasoning effort from suffixes
5. **Fallback Rules**: Apply heuristics for unknown models

Supported Model Formats
-----------------------
- **Standard**: `gpt-5.1-codex`, `gpt-5.1-codex-max`, `gpt-5.1-codex-mini`
- **With Effort**: `gpt-5.1-codex-high`, `gpt-5.1-codex-medium`
- **Provider Prefixed**: `codex/gpt-5.1-codex`, `codex-oauth/gpt-5.1-codex-max`
- **Legacy**: `gpt-5-codex`, `gpt-5-codex-max`, `gpt-5-codex-mini`
- **Simplified**: `gpt-5.1`, `gpt-5`

Model Families
--------------
- **codex-max**: High-capability reasoning models
- **codex**: Standard Codex models
- **codex-mini**: Efficient, fast models
- **gpt-5.1**: Base GPT-5.1 models
- **other**: Unrecognized models

Examples
--------
Basic model normalization:

>>> from litellm_codex_oauth_provider.model_map import normalize_model
>>> normalize_model("codex/gpt-5.1-codex-high")
'gpt-5.1-codex'

>>> normalize_model("gpt-5-codex-mini")
'gpt-5.1-codex-mini'

Prefix stripping:

>>> from litellm_codex_oauth_provider.model_map import strip_provider_prefix
>>> strip_provider_prefix("codex-oauth/gpt-5.1-codex-max")
'gpt-5.1-codex-max'

Model family classification:

>>> from litellm_codex_oauth_provider.model_map import get_model_family
>>> get_model_family("gpt-5.1-codex-high")
'codex'

Effort extraction:

>>> from litellm_codex_oauth_provider.model_map import extract_reasoning_effort_from_model
>>> extract_reasoning_effort_from_model("gpt-5.1-codex-xhigh")
'xhigh'

Notes
-----
- All lookups are case-insensitive
- Effort suffixes are preserved during normalization
- Unknown models are returned unchanged
- Model families determine reasoning constraints
- The mapping is built at module import time for performance

See Also
--------
- `reasoning`: Reasoning configuration based on model families
- `provider`: Main provider using these normalization functions
"""

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
    """Build model normalization mapping with legacy aliases.

    Creates comprehensive mappings for current models, legacy aliases, and all effort
    suffix variations. Used internally by normalize_model() for model identifier resolution.

    Returns
    -------
    dict[str, str]
        Mapping from lowercased model identifiers to canonical Codex names.
    """
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


def _strip_provider_prefix(model: str) -> str:
    """Remove LiteLLM provider prefixes from a model identifier.

    Strips common prefixes like 'codex-oauth/', 'codex/', and 'codex-' from model names.
    Used internally by normalize_model() and extract_reasoning_effort_from_model().

    Parameters
    ----------
    model : str
        Model identifier possibly containing provider prefixes.

    Returns
    -------
    str
        Model identifier with provider prefixes removed.
    """
    for prefix in ("codex-oauth/", "codex/", "codex-"):
        if model.startswith(prefix):
            return model[len(prefix) :].strip()
    return model.strip()


def normalize_model(model: str) -> str:
    """Normalize Codex model identifiers with explicit mapping and fallback rules.

    This function converts various model identifier formats into canonical Codex model
    names. It handles provider prefixes, effort suffixes, legacy aliases, and applies
    intelligent fallback rules for unknown models.

    The normalization process:
    1. Strips LiteLLM provider prefixes (codex/, codex-oauth/, codex-)
    2. Converts to lowercase for case-insensitive lookup
    3. Maps through the comprehensive MODEL_MAP dictionary
    4. Applies fallback heuristics for unknown models
    5. Returns the normalized model identifier

    Parameters
    ----------
    model : str
        The model identifier to normalize. Can be in various formats:
        - Standard: "gpt-5.1-codex", "gpt-5.1-codex-max", "gpt-5.1-codex-mini"
        - With effort: "gpt-5.1-codex-high", "gpt-5.1-codex-medium"
        - Provider prefixed: "codex/gpt-5.1-codex", "codex-oauth/gpt-5.1-codex-max"
        - Legacy: "gpt-5-codex", "gpt-5-codex-mini"
        - Simplified: "gpt-5.1"

    Returns
    -------
    str
        The normalized model identifier in canonical Codex format.

    Examples
    --------
    Basic normalization:

    >>> from litellm_codex_oauth_provider.model_map import normalize_model
    >>> normalize_model("codex/gpt-5.1-codex-high")
    'gpt-5.1-codex'

    >>> normalize_model("gpt-5-codex-mini")
    'gpt-5.1-codex-mini'

    >>> normalize_model("codex-oauth/gpt-5.1-codex-max")
    'gpt-5.1-codex-max'

    Legacy model support:

    >>> normalize_model("gpt-5")
    'gpt-5.1'

    >>> normalize_model("gpt-5-codex")
    'gpt-5.1-codex'

    Unknown models:

    >>> normalize_model("unknown-model")
    'unknown-model'

    Notes
    -----
    - The function preserves effort suffixes during normalization
    - All lookups are case-insensitive
    - Unknown models are returned unchanged (fallback behavior)
    - The MODEL_MAP is built at module import time for performance
    - Effort suffixes are extracted separately via extract_reasoning_effort_from_model

    See Also
    --------
    - `_strip_provider_prefix`: Remove provider prefixes
    - `extract_reasoning_effort_from_model`: Extract effort level
    - `get_model_family`: Get model family classification
    """
    cleaned = _strip_provider_prefix(model)
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
    """Return the Codex model family label for reasoning constraints.

    Parameters
    ----------
    normalized_model : str
        Canonical Codex model identifier.

    Returns
    -------
    str
        Family label (e.g., ``codex``, ``codex-max``, ``codex-mini``, ``gpt-5.1``, ``other``).
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
    """Infer reasoning effort from a model suffix, if present.

    Parameters
    ----------
    model : str
        Model identifier that may include an effort suffix.

    Returns
    -------
    str | None
        Effort level when detected, otherwise ``None``.
    """
    key = _strip_provider_prefix(model).lower()
    for suffix in MODEL_EFFORT_SUFFIXES:
        suffix_token = f"-{suffix}"
        if key.endswith(suffix_token):
            return suffix
    return None
