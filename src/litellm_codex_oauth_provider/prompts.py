"""System prompt handling and Codex instruction retrieval."""

from __future__ import annotations

import json
import re
import time
from collections.abc import Iterable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Final

import httpx

from . import constants
from .model_map import get_model_family

if TYPE_CHECKING:
    from pathlib import Path

DEFAULT_INSTRUCTIONS: Final[str] = "You are a helpful assistant."
LEGACY_TOOLCHAIN_MARKERS: Final[tuple[str, ...]] = (
    "toolchain system prompt",
    "toolchain::system",
    "legacy toolchain",
)
TOOL_REMAP_PROMPT: Final[
    str
] = """Tool remapping: emit tool calls using the provided OpenAI tool schema even if previous \
instructions referenced legacy tool shims."""
TOOL_BRIDGE_PROMPT: Final[str] = """# Codex Tool Bridge

You are an open-source AI coding assistant with tool support, running behind a developer CLI. \
When tools are provided, prefer invoking them via standard OpenAI tool calls, using the provided \
tool schema exactly. Do not fabricate results—issue tool calls whenever they are needed to satisfy \
the request."""

PROMPT_FILES: dict[str, str] = {
    "codex-max": "gpt-5.1-codex-max_prompt.md",
    "codex": "gpt_5_codex_prompt.md",
    "gpt-5.1": "gpt_5_1_prompt.md",
}

CACHE_FILES: dict[str, str] = {
    "codex-max": "codex-max-instructions.md",
    "codex": "codex-instructions.md",
    "gpt-5.1": "gpt-5.1-instructions.md",
}


@dataclass(slots=True)
class CacheMetadata:
    """Metadata for cached Codex instructions."""

    etag: str | None
    tag: str | None
    last_checked: float | None
    url: str | None


@dataclass(slots=True)
class CachePaths:
    """Cache locations for instructions and metadata."""

    instructions: Path
    metadata: Path


def _cache_paths(model_family: str) -> CachePaths:
    cache_dir = constants.CODEX_CACHE_DIR
    instructions_file = cache_dir / CACHE_FILES[model_family]
    meta_file = (
        cache_dir / f"{CACHE_FILES[model_family].replace('.md', constants.CODEX_CACHE_META_SUFFIX)}"
    )
    return CachePaths(instructions=instructions_file, metadata=meta_file)


def _coerce_text(content: Any) -> str:
    """Convert OpenAI content payloads to plain text for inspection."""
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, dict):
        return _coerce_text(content.get("text") or content.get("content"))
    if isinstance(content, Iterable):
        parts = [_coerce_text(part) for part in content]
        return "\n".join(part for part in parts if part)
    return str(content)


def _is_toolchain_system_prompt(content: str) -> bool:
    """Identify legacy toolchain system prompts that should be filtered in Codex mode."""
    lowered = content.lower()
    return any(marker in lowered for marker in LEGACY_TOOLCHAIN_MARKERS)


def _clean_message_payload(message: dict[str, Any]) -> dict[str, Any]:
    """Drop Codex-incompatible metadata from a message payload."""
    cleaned = {key: value for key, value in message.items() if key not in {"id", "item_reference"}}
    if (
        cleaned.get("role") == "assistant"
        and "function_call_output" in cleaned
        and "function_call" not in cleaned
    ):
        cleaned.pop("function_call_output")
    return cleaned


def _to_codex_input(message: dict[str, Any]) -> dict[str, Any]:
    """Map OpenAI message-like payloads to Codex input schema."""
    if message.get("role") == "tool":
        tool_call_id = message.get("tool_call_id")
        output = message.get("content")
        if tool_call_id is not None:
            output = {"tool_call_id": tool_call_id, "content": output}
        return {
            "type": "function_call_output",
            "output": output,
            "role": message.get("role", "assistant"),
        }
    if "tool_calls" in message:
        tool_call = (message.get("tool_calls") or [None])[0] or {}
        if isinstance(tool_call, dict):
            arguments = tool_call.get("arguments", "")
            if isinstance(arguments, (dict, list)):
                arguments = json.dumps(arguments)
            return {
                "type": "function_call",
                "function_call": {
                    "name": tool_call.get("name"),
                    "arguments": arguments,
                },
                "role": message.get("role", "assistant"),
            }
    if "function_call_output" in message:
        return {
            "type": "function_call_output",
            "output": message.get("function_call_output"),
            "role": message.get("role", "assistant"),
        }
    if "function_call" in message:
        return {
            "type": "function_call",
            "function_call": message.get("function_call"),
            "role": message.get("role", "assistant"),
        }
    return {
        "type": "message",
        "content": message.get("content"),
        "role": message.get("role", "user"),
    }


def _load_cache_metadata(paths: CachePaths) -> CacheMetadata:
    if not paths.metadata.exists():
        return CacheMetadata(etag=None, tag=None, last_checked=None, url=None)
    try:
        payload = json.loads(paths.metadata.read_text(encoding="utf-8"))
        return CacheMetadata(
            etag=payload.get("etag"),
            tag=payload.get("tag"),
            last_checked=payload.get("lastChecked"),
            url=payload.get("url"),
        )
    except Exception:
        return CacheMetadata(etag=None, tag=None, last_checked=None, url=None)


def _load_cached_instructions(paths: CachePaths) -> str | None:
    try:
        return paths.instructions.read_text(encoding="utf-8")
    except FileNotFoundError:
        return None


def _write_cache(
    paths: CachePaths,
    *,
    instructions: str,
    metadata: CacheMetadata,
) -> None:
    last_checked = metadata.last_checked if metadata.last_checked is not None else time.time()
    paths.instructions.parent.mkdir(parents=True, exist_ok=True)
    paths.instructions.write_text(instructions, encoding="utf-8")
    paths.metadata.write_text(
        json.dumps(
            {
                "etag": metadata.etag,
                "tag": metadata.tag,
                "lastChecked": last_checked,
                "url": metadata.url,
            }
        ),
        encoding="utf-8",
    )


def _latest_release_tag(client: httpx.Client) -> str:
    """Return the latest release tag, mirroring the TS fallback logic."""
    try:
        response = client.get(constants.CODEX_RELEASE_API_URL, timeout=20.0)
        if response.is_success:
            data = response.json()
            tag = data.get("tag_name")
            if isinstance(tag, str) and tag:
                return tag
    except Exception:
        ...

    html_response = client.get(constants.CODEX_RELEASE_HTML_URL, timeout=20.0)
    if not html_response.is_success:
        raise RuntimeError(f"Failed to fetch latest release: {html_response.status_code}")

    redirected_url = str(html_response.url)
    if redirected_url and "/tag/" in redirected_url:
        tag_candidate = redirected_url.split("/tag/")[-1]
        if tag_candidate and "/" not in tag_candidate:
            return tag_candidate

    match = re.search(r"/openai/codex/releases/tag/([^\"']+)", html_response.text)
    if match and match.group(1):
        return match.group(1)

    raise RuntimeError("Failed to determine latest release tag from GitHub")


def get_codex_instructions(normalized_model: str = "gpt-5.1-codex") -> str:
    """Fetch Codex instructions from the latest release with ETag-based caching."""
    model_family = get_model_family(normalized_model)
    prompt_file = PROMPT_FILES.get(model_family, PROMPT_FILES["codex"])
    paths = _cache_paths(model_family)

    metadata = _load_cache_metadata(paths)
    cached_instructions = _load_cached_instructions(paths)
    now = time.time()

    if (
        metadata.last_checked
        and cached_instructions
        and now - float(metadata.last_checked) < constants.CODEX_INSTRUCTIONS_CACHE_TTL_SECONDS
    ):
        return cached_instructions

    try:
        with httpx.Client() as client:
            latest_tag = _latest_release_tag(client)
            url = f"https://raw.githubusercontent.com/openai/codex/{latest_tag}/codex-rs/core/{prompt_file}"
            headers = {}
            if metadata.tag == latest_tag and metadata.etag:
                headers["If-None-Match"] = metadata.etag

            response = client.get(url, headers=headers, timeout=20.0)
            if response.status_code == httpx.codes.NOT_MODIFIED and cached_instructions:
                updated_metadata = CacheMetadata(
                    etag=metadata.etag, tag=latest_tag, last_checked=now, url=url
                )
                _write_cache(paths, instructions=cached_instructions, metadata=updated_metadata)
                return cached_instructions

            if response.is_success:
                instructions = response.text
                etag = response.headers.get("etag")
                updated_metadata = CacheMetadata(
                    etag=etag, tag=latest_tag, last_checked=now, url=url
                )
                _write_cache(paths, instructions=instructions, metadata=updated_metadata)
                return instructions
    except Exception:
        ...

    if cached_instructions:
        return cached_instructions
    return DEFAULT_INSTRUCTIONS


def derive_instructions(
    messages: list[dict[str, Any]], *, codex_mode: bool, normalized_model: str
) -> tuple[str, list[dict[str, Any]]]:
    """Extract instructions and convert messages into Codex `input` format."""
    system_parts: list[str] = []
    input_payload: list[dict[str, Any]] = []

    for message in messages:
        if message.get("role") == "system":
            content = _coerce_text(message.get("content"))
            if not content:
                continue
            if codex_mode and _is_toolchain_system_prompt(content):
                continue
            system_parts.append(content)
            continue

        cleaned = _clean_message_payload(message)
        input_payload.append(_to_codex_input(cleaned))

    base_instructions = (
        get_codex_instructions(normalized_model) if codex_mode else TOOL_REMAP_PROMPT
    )
    instructions_parts: list[str] = [base_instructions, *system_parts]
    instructions = "\n\n".join(part for part in instructions_parts if part) or DEFAULT_INSTRUCTIONS
    return instructions, input_payload


def build_tool_bridge_message() -> dict[str, Any]:
    """Return the Codex/OpenCode bridge developer message for tool-enabled requests."""
    return {
        "type": "message",
        "role": "developer",
        "content": [{"type": "input_text", "text": TOOL_BRIDGE_PROMPT}],
    }
