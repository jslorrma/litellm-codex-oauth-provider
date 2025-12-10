r"""Remote resource loading for Codex instructions.

This module handles fetching, caching, and managing Codex instructions from remote
sources, primarily GitHub releases. It provides intelligent caching with ETag support
and fallback mechanisms for offline operation.

The remote resources system supports:
- GitHub release-based instruction fetching
- Intelligent caching with TTL and ETag validation
- Model family-specific instruction files
- Offline fallback to cached instructions
- Cache metadata management and validation

Resource Management Pipeline
----------------------------
1. **Cache Check**: Validate existing cache freshness
2. **Release Discovery**: Fetch latest GitHub release information
3. **File Download**: Download model-specific instruction files
4. **Cache Update**: Store instructions and metadata
5. **Fallback Handling**: Use cached data when network fails

Supported Instruction Files
----------------------------
- **codex-max**: `gpt-5.1-codex-max_prompt.md` → `codex-max-instructions.md`
- **codex**: `gpt_5_codex_prompt.md` → `codex-instructions.md`
- **gpt-5.1**: `gpt_5_1_prompt.md` → `gpt-5.1-instructions.md`

Cache Strategy
--------------
- **TTL**: 15 minutes cache lifetime
- **ETag**: HTTP ETag validation for efficiency
- **Metadata**: JSON metadata file with cache information
- **Fallback**: Graceful degradation to cached data
- **Atomic**: Atomic write operations for cache consistency

Examples
--------
Basic instruction fetching:

>>> from litellm_codex_oauth_provider.remote_resources import fetch_codex_instructions
>>> instructions = fetch_codex_instructions("gpt-5.1-codex-max")
>>> print(instructions[:100])
'# GPT-5.1 Codex Max Instructions\\n\\nYou are a helpful AI coding assistant...'

Cache path management:

>>> from litellm_codex_oauth_provider.remote_resources import _cache_paths
>>> paths = _cache_paths("codex")
>>> print(f"Instructions: {paths.instructions}")
>>> print(f"Metadata: {paths.metadata}")

Cache metadata handling:

>>> from litellm_codex_oauth_provider.remote_resources import _load_cache_metadata
>>> metadata = _load_cache_metadata(paths)
>>> print(f"ETag: {metadata.etag}")
>>> print(f"Last checked: {metadata.last_checked}")

Notes
-----
- Instructions are fetched from OpenAI's official Codex repository
- Cache directory defaults to `~/.opencode/cache`
- Network timeouts are set to 20 seconds for GitHub API calls
- Cache validation uses both TTL and ETag for efficiency
- Fallback to default instructions when all else fails

See Also
--------
- `prompts`: Instruction usage in message derivation
- `constants`: Cache directory and TTL configuration
"""

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
    "gpt-5.1-codex": "codex-instructions.md",
    "gpt-5.1-codex-max": "codex-max-instructions.md",
    "gpt-5.1-codex-mini": "codex-instructions.md",
}

# Allow model-family aliases that should reuse an existing instruction file.
FAMILY_ALIASES: Final[dict[str, str]] = {
    "codex-mini": "codex",
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
    """Return cache file paths for the given model family.

    Parameters
    ----------
    model_family : str
        Model family identifier (e.g., ``codex``, ``codex-max``, ``gpt-5.1``).

    Returns
    -------
    CachePaths
        Paths for instruction and metadata files.
    """
    cache_dir = constants.CODEX_CACHE_DIR
    cache_key = FAMILY_ALIASES.get(model_family, model_family)
    if cache_key not in CACHE_FILES:
        raise ValueError(f"Model '{model_family}' not found")

    instructions_file = cache_dir / CACHE_FILES[cache_key]
    meta_suffix = constants.CODEX_CACHE_META_SUFFIX
    meta_file = cache_dir / f"{CACHE_FILES[cache_key].replace('.md', meta_suffix)}"
    return CachePaths(instructions=instructions_file, metadata=meta_file)


def _load_cache_metadata(paths: CachePaths) -> CacheMetadata:
    """Load cache metadata from disk, returning defaults on failure.

    Parameters
    ----------
    paths : CachePaths
        Named tuple containing paths to instruction and metadata files.

    Returns
    -------
    CacheMetadata
        Parsed metadata with etag, tag, last_checked timestamp, and URL.
        Returns default (all None) values if file is missing or corrupted.

    Notes
    -----
    Silently handles JSON decode errors and file I/O exceptions by returning
    default metadata values, ensuring graceful degradation when cache is invalid.
    """
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
    """Return cached instruction contents if available.

    Parameters
    ----------
    paths : CachePaths
        Named tuple containing paths to instruction and metadata files.

    Returns
    -------
    str | None
        Instruction file contents as a string, or None if file doesn't exist.

    Notes
    -----
    Only catches FileNotFoundError; other I/O errors propagate to caller.
    """
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
    """Persist instructions and metadata to disk atomically.

    Parameters
    ----------
    paths : CachePaths
        Named tuple containing paths to instruction and metadata files.
    instructions : str
        Instruction content to write to cache.
    metadata : CacheMetadata
        Metadata object containing etag, tag, last_checked, and url.
    now : float
        Current timestamp (epoch seconds) to use if last_checked is None.

    Notes
    -----
    Creates cache directory structure if it doesn't exist. Writes both files
    sequentially; while not fully atomic across both files, the metadata write
    is conditional on successful instruction write.
    """
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
    """Determine whether cached instructions remain valid based on TTL.

    Parameters
    ----------
    metadata : CacheMetadata
        Metadata object containing last_checked timestamp.
    cached : str | None
        Cached instruction content, or None if not available.
    now : float
        Current timestamp (epoch seconds) for TTL comparison.

    Returns
    -------
    bool
        True if cache is fresh and content exists, False otherwise.

    Notes
    -----
    Cache is considered valid if both metadata.last_checked and cached content
    exist, and the elapsed time since last_checked is less than the configured
    TTL (CODEX_INSTRUCTIONS_CACHE_TTL_SECONDS constant).
    """
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
    r"""Fetch Codex instructions from the latest release with ETag-based caching.

    This function retrieves model-specific instructions from OpenAI's official Codex
    repository, with intelligent caching to minimize network requests. It supports
    multiple model families and provides fallback mechanisms for offline operation.

    The fetching process:
    1. Determines the appropriate model family for the given model
    2. Checks cache validity using TTL and ETag validation
    3. Fetches latest GitHub release information
    4. Downloads model-specific instruction files
    5. Updates cache with new instructions and metadata
    6. Falls back to cached data if network fails

    Parameters
    ----------
    normalized_model : str, default "gpt-5.1-codex"
        The normalized model identifier to fetch instructions for.
        Supported models: "gpt-5.1-codex", "gpt-5.1-codex-max", "gpt-5.1-codex-mini", "gpt-5.1"

    Returns
    -------
    str
        The instruction text for the specified model. If fetching fails,
        returns cached instructions or default instructions as fallback.

    Examples
    --------
    Basic instruction fetching:

    >>> from litellm_codex_oauth_provider.remote_resources import fetch_codex_instructions
    >>> instructions = fetch_codex_instructions("gpt-5.1-codex-max")
    >>> print(instructions[:100])
    '# GPT-5.1 Codex Max Instructions\\n\\nYou are a helpful AI coding assistant...'

    Different model families:

    >>> codex_instructions = fetch_codex_instructions("gpt-5.1-codex")
    >>> mini_instructions = fetch_codex_instructions("gpt-5.1-codex-mini")
    >>> max_instructions = fetch_codex_instructions("gpt-5.1-codex-max")

    Notes
    -----
    - Instructions are fetched from OpenAI's official Codex repository
    - Cache TTL is 15 minutes to balance freshness and performance
    - ETag validation minimizes unnecessary downloads
    - Network timeouts are set to 20 seconds for reliability
    - Fallback to cached/default instructions ensures robustness
    - Cache directory defaults to ~/.opencode/cache

    See Also
    --------
    - `get_model_family`: Model family classification
    - `_cache_paths`: Cache file path management
    - `_should_use_cache`: Cache validation logic
    """
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
