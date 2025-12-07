"""Constants for the LiteLLM Codex OAuth Provider."""

from __future__ import annotations

import os
from pathlib import Path

# Default paths
_auth_file_override = os.getenv("CODEX_AUTH_FILE")
if _auth_file_override:
    DEFAULT_CODEX_AUTH_FILE = Path(_auth_file_override)
    DEFAULT_CODEX_AUTH_DIR = DEFAULT_CODEX_AUTH_FILE.parent
else:
    DEFAULT_CODEX_AUTH_DIR = Path.home() / ".codex"
    DEFAULT_CODEX_AUTH_FILE = DEFAULT_CODEX_AUTH_DIR / "auth.json"

# Cache paths
CODEX_CACHE_DIR = Path(os.getenv("CODEX_CACHE_DIR", Path.home() / ".opencode" / "cache"))
CODEX_CACHE_META_SUFFIX = "-meta.json"

# Feature flags
CODEX_MODE_ENV = "CODEX_MODE"
DEFAULT_CODEX_MODE = True

# ChatGPT backend (Codex) endpoints and headers
CODEX_API_BASE_URL = "https://chatgpt.com/backend-api"
CODEX_RESPONSES_ENDPOINT = "/codex/responses"
OPENAI_RESPONSES_ENDPOINT = "/responses"
CODEX_RELEASE_API_URL = "https://api.github.com/repos/openai/codex/releases/latest"
CODEX_RELEASE_HTML_URL = "https://github.com/openai/codex/releases/latest"
JWT_ACCOUNT_CLAIM = "https://api.openai.com/auth"
CHATGPT_ACCOUNT_HEADER = "chatgpt-account-id"
OPENAI_BETA_HEADER = "OpenAI-Beta"
OPENAI_BETA_VALUE = "responses=experimental"
OPENAI_ORIGINATOR_HEADER = "originator"
OPENAI_ORIGINATOR_VALUE = "codex_cli_rs"
SESSION_ID_HEADER = "session_id"
CONVERSATION_ID_HEADER = "conversation_id"
REASONING_INCLUDE_TARGET = "reasoning.encrypted_content"
CODEX_INSTRUCTIONS_CACHE_TTL_SECONDS = 15 * 60  # 15 minutes

# Token cache settings
TOKEN_CACHE_BUFFER_SECONDS = 300  # 5 minutes
TOKEN_DEFAULT_EXPIRY_SECONDS = 3600  # 1 hour
