"""Reasoning and verbosity configuration helpers.

This module provides reasoning effort and verbosity configuration for Codex models,
including model family-specific constraints and intelligent effort inference.

The reasoning system supports:
- Reasoning effort level validation and clamping
- Model family-specific effort constraints
- Verbosity level configuration
- Automatic effort inference from model names
- Default configuration fallbacks

Reasoning Configuration
-----------------------
1. **Effort Inference**: Extract effort from model name suffixes
2. **User Override**: Allow explicit effort specification
3. **Family Constraints**: Apply model-specific effort limits
4. **Verbosity Setting**: Configure response verbosity level
5. **Default Fallback**: Use sensible defaults when needed

Supported Effort Levels
-----------------------
- **none**: Minimal reasoning, fastest responses
- **minimal**: Very basic reasoning
- **low**: Light reasoning with basic analysis
- **medium**: Balanced reasoning (default)
- **high**: Deep reasoning with comprehensive analysis
- **xhigh**: Maximum reasoning capability

Model Family Constraints
------------------------
- **codex-max**: Supports all effort levels
- **codex**: Minimal effort clamped to low, xhigh clamped to high
- **codex-mini**: None/minimal/low clamped to medium, xhigh clamped to high
- **other**: xhigh clamped to high

Examples
--------
Basic reasoning configuration:

>>> from litellm_codex_oauth_provider.reasoning import apply_reasoning_config
>>> config = apply_reasoning_config(
...     original_model="gpt-5.1-codex-high",
...     normalized_model="gpt-5.1-codex",
...     reasoning_effort="medium",
...     verbosity="high",
... )
>>> print(config)
{'reasoning': {'effort': 'medium', 'summary': 'auto'}, 'text': {'verbosity': 'high'}}

Effort extraction from model:

>>> from litellm_codex_oauth_provider.reasoning import extract_reasoning_effort_from_model
>>> effort = extract_reasoning_effort_from_model("gpt-5.1-codex-xhigh")
>>> print(effort)
'xhigh'

Model family classification:

>>> from litellm_codex_oauth_provider.reasoning import get_model_family
>>> family = get_model_family("gpt-5.1-codex-mini")
>>> print(family)
'codex-mini'

Notes
-----
- Effort levels are case-insensitive
- Model family determines constraint application
- Unknown effort levels default to medium
- Verbosity affects response detail level
- Configuration is applied before sending to Codex API

See Also
--------
- `model_map`: Model family classification functions
- `provider`: Main provider applying reasoning configuration
"""

from __future__ import annotations

from typing import Any, Final

from .model_map import extract_reasoning_effort_from_model, get_model_family

DEFAULT_REASONING_EFFORT: Final[str] = "medium"
DEFAULT_VERBOSITY: Final[str] = "medium"
DEFAULT_REASONING_SUMMARY: Final[str] = "auto"
VALID_EFFORTS: Final[set[str]] = {
    "none",
    "minimal",
    "low",
    "medium",
    "high",
    "xhigh",
}


def _coerce_effort(reasoning_effort: Any) -> str | None:
    """Extract a string reasoning effort from supported input shapes.

    Parameters
    ----------
    reasoning_effort : Any
        Effort value provided by the caller, optionally as a dict with an ``effort``
        key or a plain string.

    Returns
    -------
    str | None
        Lowercased effort value if recognized, otherwise ``None``.
    """
    if isinstance(reasoning_effort, str):
        return reasoning_effort.lower()
    if isinstance(reasoning_effort, dict):
        value = reasoning_effort.get("effort")
        if isinstance(value, str):
            return value.lower()
    return None


def _clamp_effort(family: str, effort: str) -> str:
    """Apply model-family-specific reasoning effort constraints.

    Parameters
    ----------
    family : str
        Model family classification (e.g., ``codex``, ``codex-max``, ``codex-mini``).
    effort : str
        Requested reasoning effort level.

    Returns
    -------
    str
        Adjusted effort that respects family limitations.
    """
    clamped = effort
    if family == "codex-mini":
        if effort in {"none", "minimal", "low"}:
            clamped = "medium"
        elif effort == "xhigh":
            clamped = "high"
    elif family == "codex":
        if effort == "minimal":
            clamped = "low"
        elif effort == "xhigh":
            clamped = "high"
    elif family != "codex-max" and effort == "xhigh":
        clamped = "high"
    return clamped


def apply_reasoning_config(
    *,
    original_model: str,
    normalized_model: str,
    reasoning_effort: Any | None,
    verbosity: str | None,
) -> dict[str, dict[str, str]]:
    """Return reasoning/text config honoring Codex family constraints.

    Parameters
    ----------
    original_model : str
        Model identifier as provided by the caller (may include effort suffix).
    normalized_model : str
        Codex-normalized model identifier.
    reasoning_effort : Any | None
        Optional effort provided by caller; may be string or dict with ``effort`` key.
    verbosity : str | None
        Optional verbosity level override.

    Returns
    -------
    dict[str, dict[str, str]]
        Dictionary with ``reasoning`` and ``text`` configuration blocks.

    Notes
    -----
    Effort is inferred from the original model when not provided explicitly and is
    clamped to family-supported ranges to prevent API errors.
    """
    inferred_effort = extract_reasoning_effort_from_model(original_model)
    provided_effort = _coerce_effort(reasoning_effort)
    effort = (provided_effort or inferred_effort or DEFAULT_REASONING_EFFORT).lower()
    effort = effort if effort in VALID_EFFORTS else DEFAULT_REASONING_EFFORT

    family = get_model_family(normalized_model)
    clamped_effort = _clamp_effort(family, effort)
    resolved_verbosity = (verbosity or DEFAULT_VERBOSITY).lower()

    return {
        "reasoning": {"effort": clamped_effort, "summary": DEFAULT_REASONING_SUMMARY},
        "text": {"verbosity": resolved_verbosity},
    }
