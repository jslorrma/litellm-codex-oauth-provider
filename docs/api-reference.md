# API Reference

This document provides comprehensive API reference for the LiteLLM Codex OAuth Provider, covering all public interfaces and internal implementation details with the new OpenAI client architecture.

## Public API

### CodexAuthProvider Class

The main entry point for the provider. This class implements the LiteLLM `CustomLLM` interface and uses the official OpenAI client library.

```python
from litellm_codex_oauth_provider import CodexAuthProvider

provider = CodexAuthProvider()
```

#### Constructor

```python
def __init__(self) -> None
```

Initializes the provider with OpenAI client integration and default configuration.

**Attributes:**
- `base_url`: Base URL for Codex API
- `_cached_token`: Cached bearer token (internal)
- `_token_expiry`: Token expiry timestamp (internal)
- `_account_id`: Cached ChatGPT account ID (internal)
- `_codex_mode_enabled`: Feature flag for Codex-specific behavior
- `_client`: Synchronous OpenAI client instance
- `_async_client`: Asynchronous OpenAI client instance

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

Main completion method implementing LiteLLM interface with OpenAI client delegation.

**Parameters:**
- `model`: Model identifier (supports `codex/` prefix)
- `messages`: List of message dictionaries with `role` and `content`
- `api_base`: Optional custom API base URL
- `custom_llm_provider`: Reserved parameter for LiteLLM interface
- `**kwargs`: Additional LiteLLM parameters

**Supported kwargs:**
- `prompt_cache_key`: Session caching key
- `tools`: List of OpenAI-style tool definitions
- `tool_choice`: Tool selection strategy
- `parallel_tool_calls`: Enable parallel tool execution
- `metadata`: Additional metadata
- `user`: User identifier
- `reasoning_effort`: Reasoning effort level
- `verbosity`: Response verbosity level

**Note:** The following parameters are automatically filtered out as they're not supported by the Codex responses endpoint:
- `max_tokens`, `max_output_tokens`
- `temperature`
- `safety_identifier`
- `prompt_cache_retention`
- `truncation`
- `top_logprobs`
- `top_p`
- `service_tier`
- `max_tool_calls`
- `background`

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
    metadata={"source": "example"}
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

Asynchronous completion method using async OpenAI client.

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

Streaming completion method (simulated streaming with single chunk).

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

### OpenAI Client Module (`openai_client.py`)

#### _BaseCodexClient Class

```python
class _BaseCodexClient(OpenAI):
    def __init__(
        self,
        *,
        token_provider: Callable[[], str],
        account_id_provider: Callable[[], str | None],
        base_url: str,
        timeout: float = 60.0,
        http_client: httpx.Client | None = None,
        **kwargs: Any,
    ) -> None
```

Base class for Codex-aware OpenAI clients with custom authentication.

**Parameters:**
- `token_provider`: Function that returns the current bearer token
- `account_id_provider`: Function that returns the current account ID
- `base_url`: Base URL for the API
- `timeout`: Request timeout in seconds
- `http_client`: Optional custom httpx client
- `**kwargs`: Additional arguments passed to OpenAI client

#### CodexOpenAIClient Class

```python
class CodexOpenAIClient(_BaseCodexClient)
```

Synchronous Codex-aware OpenAI client.

**Features:**
- Automatic token injection via token provider
- Custom header injection for Codex API
- Account ID resolution and injection
- OpenAI beta headers for experimental features

#### AsyncCodexOpenAIClient Class

```python
class AsyncCodexOpenAIClient(AsyncOpenAI)
```

Asynchronous Codex-aware OpenAI client.

**Features:** Same as `CodexOpenAIClient` but for async operations.

### Response Adapter Module (`adapter.py`)

#### transform_response()

```python
def transform_response(openai_response: dict[str, Any], model: str) -> ModelResponse
```

Transforms OpenAI API response to LiteLLM format.

**Parameters:**
- `openai_response`: Response from OpenAI/Codex API
- `model`: Model identifier for the response

**Returns:** `ModelResponse` in LiteLLM format

**Features:**
- OpenAI typed model validation
- Multiple response format support
- Tool call extraction and normalization
- Usage statistics calculation

#### parse_response_body()

```python
def parse_response_body(response: httpx.Response) -> dict[str, Any]
```

Parses HTTP response body handling multiple formats.

**Parameters:**
- `response`: httpx Response object

**Returns:** Parsed response data as dictionary

**Features:**
- SSE (Server-Sent Events) detection and parsing
- JSON response handling
- OpenAI typed model validation with fallbacks

#### convert_sse_to_json()

```python
def convert_sse_to_json(payload: str) -> dict[str, Any]
```

Converts buffered SSE text to final JSON payload.

**Parameters:**
- `payload`: Raw SSE text data

**Returns:** Parsed JSON response

**Features:**
- Event stream parsing
- OpenAI typed model validation
- Fallback to manual parsing if validation fails

#### build_streaming_chunk()

```python
def build_streaming_chunk(response: ModelResponse) -> GenericStreamingChunk
```

Builds a minimal streaming chunk from a completed response.

**Parameters:**
- `response`: Completed ModelResponse

**Returns:** GenericStreamingChunk for streaming simulation

### Remote Resources Module (`remote_resources.py`)

#### fetch_codex_instructions()

```python
def fetch_codex_instructions(normalized_model: str = "gpt-5.1-codex") -> str
```

Fetches Codex instructions from GitHub with caching.

**Parameters:**
- `normalized_model`: Target model for instruction selection

**Returns:** Instruction text

**Features:**
- ETag-based caching with 15-minute TTL
- GitHub API integration for latest releases
- Fallback to cached or default instructions
- Model family-based instruction selection

#### CacheMetadata Class

```python
@dataclass(slots=True)
class CacheMetadata:
    etag: str | None
    tag: str | None
    last_checked: float | None
    url: str | None
```

Metadata for cached Codex instructions.

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
    instructions_text: str | None = None,
) -> tuple[str, list[dict[str, Any]]]
```

Extracts instructions and converts messages to Codex input format.

**Parameters:**
- `messages`: OpenAI-style message list
- `codex_mode`: Enable Codex-specific processing
- `normalized_model`: Target model for instruction selection
- `instructions_text`: Pre-fetched instructions (optional)

**Returns:** Tuple of (instructions, filtered_messages)

**Message transformations:**
- System messages → Instructions (filtered for toolchain prompts)
- User messages → Direct conversion
- Assistant messages → Direct conversion
- Tool messages → `function_call_output` format

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
| `CODEX_DEBUG` | `bool` | `False` | Enable debug logging |

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
    metadata={"source": "analysis_tool"},
    user="user123"
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

## Customization

### Custom OpenAI Client

```python
from litellm_codex_oauth_provider.openai_client import CodexOpenAIClient
from openai._base_client import FinalRequestOptions
import httpx

class CustomCodexClient(CodexOpenAIClient):
    def _prepare_options(self, options: FinalRequestOptions) -> FinalRequestOptions:
        prepared = super()._prepare_options(options)
        headers = httpx.Headers(prepared.headers or {})
        headers["Custom-Header"] = "custom-value"
        return prepared.copy(update={"headers": headers})
```

### Custom Response Adapter

```python
from litellm_codex_oauth_provider.adapter import transform_response
from litellm import ModelResponse

def custom_transform_response(openai_response: dict[str, Any], model: str) -> ModelResponse:
    # Custom transformation logic here
    return transform_response(openai_response, model)
```

### Custom Model Mapping

```python
# Extend model_map.py
alias_bases = {
    "custom-model": "target-base-model",
    # ... more aliases
}
```
