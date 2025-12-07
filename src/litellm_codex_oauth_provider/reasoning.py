"""Reasoning and verbosity configuration helpers."""

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
    """Extract a string reasoning effort from supported input shapes."""
    if isinstance(reasoning_effort, str):
        return reasoning_effort.lower()
    if isinstance(reasoning_effort, dict):
        value = reasoning_effort.get("effort")
        if isinstance(value, str):
            return value.lower()
    return None


def _clamp_effort(family: str, effort: str) -> str:
    """Apply model-family-specific reasoning effort constraints."""
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
    """Return reasoning/text config honoring Codex family constraints."""
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
