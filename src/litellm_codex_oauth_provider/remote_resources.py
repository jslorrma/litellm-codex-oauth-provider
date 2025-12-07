"""Remote resource loading for Codex instructions."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, Final

import httpx

from . import constants
from .model_map import get_model_family

if TYPE_CHECKING:
    from pathlib import Path

PROMPT_FILES: Final[dict[str, str]] = {
    "codex-max": "gpt-5.1-codex-max_prompt.md",
    "codex": "gpt_5_codex_prompt.md",
    "gpt-5.1": "gpt_5_1_prompt.md",
}

CACHE_FILES: Final[dict[str, str]] = {
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
    meta_suffix = constants.CODEX_CACHE_META_SUFFIX
    meta_file = cache_dir / f"{CACHE_FILES[model_family].replace('.md', meta_suffix)}"
    return CachePaths(instructions=instructions_file, metadata=meta_file)


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
    except (json.JSONDecodeError, OSError):
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
    now: float,
) -> None:
    last_checked = metadata.last_checked if metadata.last_checked is not None else now
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


def _should_use_cache(metadata: CacheMetadata, cached: str | None, now: float) -> bool:
    if metadata.last_checked is None or cached is None:
        return False
    return now - float(metadata.last_checked) < constants.CODEX_INSTRUCTIONS_CACHE_TTL_SECONDS


def _latest_release_tag(client: httpx.Client) -> str:
    """Return the latest release tag from the GitHub API."""
    response = client.get(constants.CODEX_RELEASE_API_URL, timeout=20.0)
    response.raise_for_status()
    payload = response.json()
    tag = payload.get("tag_name")
    if not isinstance(tag, str) or not tag:
        raise ValueError("Missing release tag in GitHub API response")
    return tag


def fetch_codex_instructions(normalized_model: str = "gpt-5.1-codex") -> str:
    """Fetch Codex instructions from the latest release with ETag-based caching."""
    model_family = get_model_family(normalized_model)
    prompt_file = PROMPT_FILES.get(model_family, PROMPT_FILES["codex"])
    paths = _cache_paths(model_family)

    metadata = _load_cache_metadata(paths)
    cached_instructions = _load_cached_instructions(paths)
    now = time.time()

    if _should_use_cache(metadata, cached_instructions, now):
        return cached_instructions or constants.DEFAULT_INSTRUCTIONS

    try:
        with httpx.Client() as client:
            latest_tag = _latest_release_tag(client)
            url = (
                "https://raw.githubusercontent.com/openai/codex/"
                f"{latest_tag}/codex-rs/core/{prompt_file}"
            )
            headers = {}
            if metadata.tag == latest_tag and metadata.etag:
                headers["If-None-Match"] = metadata.etag

            response = client.get(url, headers=headers, timeout=20.0)
            if response.status_code == httpx.codes.NOT_MODIFIED and cached_instructions:
                updated_metadata = CacheMetadata(
                    etag=metadata.etag, tag=latest_tag, last_checked=now, url=url
                )
                _write_cache(
                    paths, instructions=cached_instructions, metadata=updated_metadata, now=now
                )
                return cached_instructions

            response.raise_for_status()
            instructions = response.text
            etag = response.headers.get("etag")
            updated_metadata = CacheMetadata(etag=etag, tag=latest_tag, last_checked=now, url=url)
            _write_cache(paths, instructions=instructions, metadata=updated_metadata, now=now)
            return instructions
    except (httpx.RequestError, httpx.HTTPStatusError, ValueError, json.JSONDecodeError):
        if cached_instructions:
            return cached_instructions
        return constants.DEFAULT_INSTRUCTIONS

    return cached_instructions or constants.DEFAULT_INSTRUCTIONS
