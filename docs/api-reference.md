# API Reference

This document provides comprehensive API reference for the LiteLLM Codex OAuth Provider, covering all public interfaces and internal implementation details.

## Public API

### CodexAuthProvider Class

The main entry point for the provider. This class implements the LiteLLM `CustomLLM` interface.

```python
from litellm_codex_oauth_provider import CodexAuthProvider

provider = CodexAuthProvider()
```

#### Constructor

```python
def __init__(self) -> None
```

Initializes the provider with default configuration.

**Attributes:**
- `base_url`: Base URL for Codex API
- `_cached_token`: Cached bearer token (internal)
- `_token_expiry`: Token expiry timestamp (internal)
- `_account_id`: Cached ChatGPT account ID (internal)
- `_codex_mode_enabled`: Feature flag for Codex-specific behavior

#### Public Methods

##### completion()

```python
def completion(
    self,
    model: str,
    messages: list[dict[str, Any]],
    api_base: str | None = None,
    custom_llm_provider: str | None = None,
    **kwargs: Any,
) -> ModelResponse
```

Main completion method implementing LiteLLM interface.

**Parameters:**
- `model`: Model identifier (supports `codex/` prefix)
- `messages`: List of message dictionaries with `role` and `content`
- `api_base`: Optional custom API base URL
- `custom_llm_provider`: Reserved parameter for LiteLLM interface
- `**kwargs`: Additional LiteLLM parameters

**Supported kwargs:**
- `prompt_cache_key`: Session caching key
- `temperature`: Response creativity (0.0-2.0)
- `max_tokens` / `max_output_tokens`: Maximum response length
- `tools`: List of OpenAI-style tool definitions
- `tool_choice`: Tool selection strategy
- `parallel_tool_calls`: Enable parallel tool execution
- `frequency_penalty`: Frequency penalty for repetition
- `presence_penalty`: Presence penalty for new topics
- `logprobs`: Include log probabilities
- `top_logprobs`: Number of top log probabilities
- `metadata`: Additional metadata
- `response_format`: Response format specification
- `seed`: Random seed for reproducibility
- `stop`: Stop sequences
- `top_p`: Nucleus sampling parameter
- `user`: User identifier

**Returns:**
- `ModelResponse`: LiteLLM-compatible response object

**Raises:**
- `RuntimeError`: For HTTP errors or API failures
- `ValueError`: For invalid tool definitions

**Example:**
```python
response = provider.completion(
    model="codex/gpt-5.1-codex-max",
    messages=[
        {"role": "user", "content": "Explain quantum computing"}
    ],
    temperature=0.7,
    max_tokens=1000
)
```

##### acompletion()

```python
async def acompletion(
    self,
    model: str,
    messages: list[dict[str, Any]],
    api_base: str | None = None,
    **kwargs: Any,
) -> ModelResponse
```

Asynchronous completion method.

**Parameters:** Same as `completion()`

**Returns:** `ModelResponse` (awaited)

**Example:**
```python
import asyncio

async def main():
    response = await provider.acompletion(
        model="codex/gpt-5.1-codex",
        messages=[{"role": "user", "content": "Hello"}]
    )
    return response

result = asyncio.run(main())
```

##### streaming()

```python
def streaming(
    self,
    model: str,
    messages: list[dict[str, Any]],
    api_base: str | None = None,
    custom_llm_provider: str | None = None,
    **kwargs: Any,
) -> CustomStreamWrapper
```

Streaming completion method.

**Parameters:** Same as `completion()`

**Returns:** `CustomStreamWrapper` for streaming responses

**Example:**
```python
stream = provider.streaming(
    model="codex/gpt-5.1-codex-mini",
    messages=[{"role": "user", "content": "Count to 10"}]
)

for chunk in stream:
    print(chunk.text, end="")
```

##### astreaming()

```python
async def astreaming(
    self,
    model: str,
    messages: list[dict[str, Any]],
    api_base: str | None = None,
    custom_llm_provider: str | None = None,
    **kwargs: Any,
) -> CustomStreamWrapper
```

Asynchronous streaming method.

**Returns:** `CustomStreamWrapper` (awaited)

#### Properties

##### cached_token

```python
@property
def cached_token(self) -> str | None
```

Returns the cached bearer token if available.

##### token_expiry

```python
@property
def token_expiry(self) -> float | None
```

Returns the cached token expiry timestamp.

##### account_id

```python
@property
def account_id(self) -> str | None
```

Returns the cached ChatGPT account ID.

## Internal API

### Authentication Module (`auth.py`)

#### AuthContext Class

```python
@dataclass(frozen=True)
class AuthContext:
    access_token: str
    account_id: str
```

Immutable authentication context container.

#### get_auth_context()

```python
def get_auth_context() -> AuthContext
```

Main entry point for authentication.

**Returns:** `AuthContext` with token and account ID

**Raises:**
- `CodexAuthFileNotFoundError`: If auth file missing
- `CodexAuthTokenExpiredError`: If token expired
- `CodexAuthTokenError`: For other token issues

#### _extract_bearer_token()

```python
def _extract_bearer_token() -> str
```

Extracts OAuth bearer token from auth file.

**Returns:** Bearer token string

**Raises:** Various auth-related exceptions

#### _decode_account_id()

```python
def _decode_account_id(access_token: str) -> str
```

Decodes ChatGPT account ID from JWT token.

**Parameters:**
- `access_token`: JWT access token

**Returns:** Account ID string

**Raises:** `CodexAuthTokenError` if decoding fails

#### _refresh_token()

```python
def _refresh_token() -> str
```

Refreshes expired OAuth token via OpenAI API.

**Returns:** New access token

**Raises:** `CodexAuthRefreshError` if refresh fails

### Model Mapping Module (`model_map.py`)

#### normalize_model()

```python
def normalize_model(model: str) -> str
```

Normalizes model identifiers to Codex-compatible names.

**Parameters:**
- `model`: Input model string (may include prefixes)

**Returns:** Normalized model identifier

**Examples:**
```python
normalize_model("codex/gpt-5.1-codex-low")  # -> "gpt-5.1-codex"
normalize_model("codex-oauth/gpt-5-codex-high")  # -> "gpt-5.1-codex"
normalize_model("gpt-5.1-codex-mini")  # -> "gpt-5.1-codex-mini"
```

#### strip_provider_prefix()

```python
def strip_provider_prefix(model: str) -> str
```

Removes LiteLLM provider prefixes from model identifiers.

**Parameters:**
- `model`: Model string with potential prefixes

**Returns:** Model string with prefixes removed

**Supported prefixes:**
- `codex/`
- `codex-oauth/`
- `codex-`

#### get_model_family()

```python
def get_model_family(normalized_model: str) -> str
```

Returns the model family label for reasoning constraints.

**Parameters:**
- `normalized_model`: Normalized model identifier

**Returns:** Family label (`codex-max`, `codex-mini`, `codex`, `gpt-5.1`, `other`)

#### extract_reasoning_effort_from_model()

```python
def extract_reasoning_effort_from_model(model: str) -> str | None
```

Infers reasoning effort from model suffix.

**Parameters:**
- `model`: Model string

**Returns:** Effort level or `None`

**Supported efforts:** `none`, `minimal`, `low`, `medium`, `high`, `xhigh`

### Prompt Management Module (`prompts.py`)

#### derive_instructions()

```python
def derive_instructions(
    messages: list[dict[str, Any]],
    *,
    codex_mode: bool,
    normalized_model: str,
) -> tuple[str, list[dict[str, Any]]]
```

Extracts instructions and converts messages to Codex input format.

**Parameters:**
- `messages`: OpenAI-style message list
- `codex_mode`: Enable Codex-specific processing
- `normalized_model`: Target model for instruction selection

**Returns:** Tuple of (instructions, filtered_messages)

**Message transformations:**
- System messages → Instructions (filtered for toolchain prompts)
- User messages → Direct conversion
- Assistant messages → Direct conversion
- Tool messages → `function_call_output` format

#### get_codex_instructions()

```python
def get_codex_instructions(normalized_model: str = "gpt-5.1-codex") -> str
```

Fetches Codex instructions from GitHub with caching.

**Parameters:**
- `normalized_model`: Target model for instruction selection

**Returns:** Instruction text

**Caching:** 15-minute TTL with ETag support

#### build_tool_bridge_message()

```python
def build_tool_bridge_message() -> dict[str, Any]
```

Creates the tool bridge developer message for tool-enabled requests.

**Returns:** Codex-compatible message dictionary

### Reasoning Configuration Module (`reasoning.py`)

#### apply_reasoning_config()

```python
def apply_reasoning_config(
    *,
    original_model: str,
    normalized_model: str,
    reasoning_effort: Any | None,
    verbosity: str | None,
) -> dict[str, dict[str, str]]
```

Applies model-specific reasoning constraints.

**Parameters:**
- `original_model`: Original model string (for effort extraction)
- `normalized_model`: Normalized model (for family detection)
- `reasoning_effort`: Explicit effort setting
- `verbosity`: Response verbosity level

**Returns:** Configuration dictionary with `reasoning` and `text` sections

**Effort clamping:**
- `codex-mini`: `none/minimal/low` → `medium`, `xhigh` → `high`
- `codex`: `minimal` → `low`, `xhigh` → `high`
- Other: `xhigh` → `high`

### Constants Module (`constants.py`)

#### Key Constants

```python
# API Configuration
CODEX_API_BASE_URL = "https://chatgpt.com/backend-api"
CODEX_RESPONSES_ENDPOINT = "/codex/responses"

# Authentication
JWT_ACCOUNT_CLAIM = "https://api.openai.com/auth"
CHATGPT_ACCOUNT_HEADER = "chatgpt-account-id"

# Feature Flags
CODEX_MODE_ENV = "CODEX_MODE"
DEFAULT_CODEX_MODE = True

# Caching
CODEX_CACHE_DIR = Path.home() / ".opencode" / "cache"
CODEX_INSTRUCTIONS_CACHE_TTL_SECONDS = 15 * 60

# Token Management
TOKEN_CACHE_BUFFER_SECONDS = 300
TOKEN_DEFAULT_EXPIRY_SECONDS = 3600
```

## Exception Hierarchy

### Base Exception

```python
class CodexAuthError(Exception)
```

Base exception for all authentication-related errors.

### Specific Exceptions

```python
class CodexAuthFileNotFoundError(CodexAuthError)
"""Raised when the Codex auth file is not found."""

class CodexAuthTokenError(CodexAuthError)
"""Raised when there's an issue with the Codex auth token."""

class CodexAuthTokenExpiredError(CodexAuthTokenError)
"""Raised when the Codex auth token has expired."""

class CodexAuthRefreshError(CodexAuthError)
"""Raised when token refresh fails."""
```

## Configuration

### Environment Variables

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `CODEX_AUTH_FILE` | `Path` | `~/.codex/auth.json` | Auth file location |
| `CODEX_CACHE_DIR` | `Path` | `~/.opencode/cache` | Cache directory |
| `CODEX_MODE` | `bool` | `True` | Enable Codex features |

### Model Configuration

#### Supported Models

| Model | Family | Max Effort | Notes |
|-------|--------|------------|-------|
| `gpt-5.1-codex` | `codex` | `high` | Standard Codex model |
| `gpt-5.1-codex-max` | `codex-max` | `xhigh` | Maximum capability |
| `gpt-5.1-codex-mini` | `codex-mini` | `high` | Efficient variant |
| `gpt-5.1` | `gpt-5.1` | `high` | Base GPT model |

#### Model Aliases

| Alias | Normalizes To |
|-------|---------------|
| `gpt-5-codex` | `gpt-5.1-codex` |
| `gpt-5-codex-max` | `gpt-5.1-codex-max` |
| `gpt-5-codex-mini` | `gpt-5.1-codex-mini` |
| `gpt-5` | `gpt-5.1` |

#### Effort Suffixes

All models support effort suffixes: `-none`, `-minimal`, `-low`, `-medium`, `-high`, `-xhigh`

## Usage Examples

### Basic Completion

```python
from litellm_codex_oauth_provider import CodexAuthProvider

provider = CodexAuthProvider()

response = provider.completion(
    model="codex/gpt-5.1-codex",
    messages=[
        {"role": "user", "content": "Write a Python function to calculate fibonacci numbers"}
    ]
)

print(response.choices[0].message.content)
```

### With Tools

```python
tools = [
    {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "Get weather information",
            "parameters": {
                "type": "object",
                "properties": {
                    "location": {"type": "string"}
                }
            }
        }
    }
]

response = provider.completion(
    model="codex/gpt-5.1-codex-max",
    messages=[{"role": "user", "content": "What's the weather in Tokyo?"}],
    tools=tools,
    tool_choice="auto"
)
```

### Streaming Response

```python
stream = provider.streaming(
    model="codex/gpt-5.1-codex-mini",
    messages=[{"role": "user", "content": "Tell me a story about a robot"}]
)

for chunk in stream:
    if chunk.text:
        print(chunk.text, end="", flush=True)
```

### Async Usage

```python
import asyncio

async def async_completion():
    response = await provider.acompletion(
        model="codex/gpt-5.1-codex-max",
        messages=[{"role": "user", "content": "Explain machine learning"}]
    )
    return response

result = asyncio.run(async_completion())
```

### Custom Configuration

```python
response = provider.completion(
    model="codex/gpt-5.1-codex-low",
    messages=[{"role": "user", "content": "Analyze this data"}],
    temperature=0.3,
    max_output_tokens=2000,
    frequency_penalty=0.1,
    presence_penalty=0.1,
    metadata={"source": "analysis_tool"}
)
```

## Error Handling

### Common Error Scenarios

```python
try:
    response = provider.completion(
        model="codex/gpt-5.1-codex",
        messages=[{"role": "user", "content": "Hello"}]
    )
except RuntimeError as e:
    if "Codex API error 401" in str(e):
        print("Authentication failed - check Codex login")
    elif "Codex API error 429" in str(e):
        print("Rate limited - retry later")
    elif "Codex API error 500" in str(e):
        print("Server error - try again later")
    else:
        print(f"API error: {e}")
except ValueError as e:
    print(f"Invalid input: {e}")
except Exception as e:
    print(f"Unexpected error: {e}")
```

### Authentication Errors

```python
from litellm_codex_oauth_provider.exceptions import (
    CodexAuthFileNotFoundError,
    CodexAuthTokenExpiredError,
    CodexAuthRefreshError
)

try:
    provider.get_bearer_token()
except CodexAuthFileNotFoundError:
    print("Run 'codex login' first")
except CodexAuthTokenExpiredError:
    print("Token expired - run 'codex login' to refresh")
except CodexAuthRefreshError:
    print("Token refresh failed - check network connection")
```
