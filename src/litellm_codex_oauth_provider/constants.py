"""Constants for the LiteLLM Codex OAuth Provider.

This module defines all configuration constants, default values, and system parameters
used throughout the Codex OAuth provider. Constants are organized by functional area
for easy maintenance and configuration.

The constants system includes:
- Default configuration values and paths
- API endpoint URLs and headers
- Feature flags and mode settings
- Cache configuration and TTL values
- Token management parameters

Configuration Categories
------------------------
1. **Authentication**: Auth file paths and token settings
2. **API Configuration**: Base URLs, endpoints, and headers
3. **Cache Settings**: Cache directories, TTL, and metadata
4. **Feature Flags**: Mode settings and debug options
5. **Token Management**: Cache buffers and expiry times

Default Paths
-------------
- **Auth File**: `~/.codex/auth.json` (configurable via CODEX_AUTH_FILE)
- **Cache Directory**: `~/.opencode/cache` (configurable via CODEX_CACHE_DIR)
- **Cache Metadata**: JSON files with ETag and timestamp information

API Configuration
-----------------
- **Base URL**: `https://chatgpt.com/backend-api`
- **Responses Endpoint**: `/codex/responses`
- **GitHub Releases**: `https://api.github.com/repos/openai/codex/releases/latest`
- **OAuth Token**: `https://auth.openai.com/oauth/token`

Headers and Features
--------------------
- **Beta Features**: `OpenAI-Beta: responses=experimental`
- **Originator**: `originator: codex_cli_rs`
- **Account ID**: `chatgpt-account-id` header
- **Reasoning**: `reasoning.encrypted_content` inclusion

Examples
--------
Accessing configuration:

>>> from litellm_codex_oauth_provider import constants
>>> print(constants.CODEX_API_BASE_URL)
'https://chatgpt.com/backend-api'
>>> print(constants.DEFAULT_CODEX_AUTH_FILE)
PosixPath('~/.codex/auth.json')

Environment variable overrides:

>>> import os
>>> os.environ["CODEX_AUTH_FILE"] = "/custom/path/auth.json"
>>> from litellm_codex_oauth_provider import constants
>>> print(constants.DEFAULT_CODEX_AUTH_FILE)
PosixPath('/custom/path/auth.json')

Cache configuration:

>>> print(f"Cache TTL: {constants.CODEX_INSTRUCTIONS_CACHE_TTL_SECONDS} seconds")
Cache TTL: 900 seconds
>>> print(f"Token buffer: {constants.TOKEN_CACHE_BUFFER_SECONDS} seconds")
Token buffer: 300 seconds

Notes
-----
- All paths use pathlib.Path for cross-platform compatibility
- Environment variables override default values
- Cache TTL is set to 15 minutes for instructions
- Token cache buffer is 5 minutes before expiry
- Debug logging controlled via CODEX_DEBUG environment variable

See Also
--------
- `auth`: Authentication using auth file constants
- `remote_resources`: Cache management using cache constants
- `openai_client`: API configuration using endpoint constants
"""

from __future__ import annotations

import os
from pathlib import Path

# Defaults
DEFAULT_INSTRUCTIONS = "You are a helpful assistant."

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
