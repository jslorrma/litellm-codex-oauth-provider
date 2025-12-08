# Codex API Integration Details

This document provides comprehensive details about how the provider wraps the Codex backend API using the official OpenAI client library, including request/response handling, authentication flow, and internal processing details.

## Codex Backend API Overview

The provider acts as a sophisticated adapter between LiteLLM's OpenAI-compatible interface and the ChatGPT backend API through the official OpenAI client library. It handles the complete request/response lifecycle while maintaining compatibility with both systems.

## OpenAI Client Integration Architecture

### Custom OpenAI Client Implementation

The provider uses a custom OpenAI client that extends the official OpenAI client with Codex-specific authentication and header injection:

```mermaid
graph TD
    A[CodexAuthProvider] --> B[CodexOpenAIClient]
    A --> C[AsyncCodexOpenAIClient]

    B --> D[_BaseCodexClient]
    C --> E[AsyncOpenAI]

    D --> F[Custom Auth Headers]
    E --> G[Custom Auth Headers]

    F --> H[Token Provider Pattern]
    G --> H
    H --> I[Account ID Provider]

    D --> J[Header Injection Override]
    E --> J
    J --> K[OpenAI Beta Headers]
    J --> L[Content-Type Headers]
    J --> M[Accept Headers]
    J --> N[Authorization Headers]
```

### Token Provider Pattern

The OpenAI client uses a token provider pattern for dynamic authentication:

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
    ) -> None:
        # Initialize with empty API key - we'll inject auth headers
        super().__init__(
            api_key="",
            base_url=base_url,
            timeout=timeout,
            http_client=client,
            **kwargs,
        )
        self._token_provider = token_provider
        self._account_id_provider = account_id_provider
```

### Custom Header Injection

The provider overrides the `_prepare_options` method to inject Codex-specific headers:

```python
@override
def _prepare_options(self, options: FinalRequestOptions) -> FinalRequestOptions:
    prepared = super()._prepare_options(options)
    headers = httpx.Headers(prepared.headers or {})

    # Inject dynamic token
    token = self._token_provider()
    if token:
        headers["Authorization"] = f"Bearer {token}"

    # Inject Codex-specific headers
    headers.setdefault("OpenAI-Beta", "responses=experimental")
    headers.setdefault("originator", "codex_cli_rs")
    headers.setdefault("Content-Type", "application/json")
    headers["Accept"] = "text/event-stream"

    # Inject account ID if available
    account_id = self._account_id_provider() or ""
    if account_id:
        headers.setdefault("chatgpt-account-id", account_id)

    return prepared.copy(update={"headers": headers})
```

## Request Processing Details

### Model Normalization Process

The provider performs intelligent model name normalization to map LiteLLM model strings to Codex-compatible identifiers:

```mermaid
graph TD
    A[Input Model String] --> B[strip_provider_prefix]
    B --> C[Remove codex/, codex-oauth/, codex-]
    C --> D[normalize_model]
    D --> E[MODEL_MAP lookup]
    E --> F[Alias resolution]
    F --> G[Fallback rules]
    G --> H[Final normalized model]

    I[codex/gpt-5.1-codex-low] --> B
    J[codex-oauth/gpt-5-codex-high] --> B
    K[gpt-5.1-codex-mini] --> B

    H --> L[gpt-5.1-codex]
    H --> M[gpt-5.1-codex]
    H --> N[gpt-5.1-codex-mini]
```

### Request Payload Construction

The provider transforms LiteLLM parameters into Codex API payloads:

```python
def _build_payload(
    self,
    *,
    model: str,
    instructions: str,
    messages: list[dict[str, Any]],
    prompt_cache_key: str | None,
    reasoning_config: dict[str, Any],
    **kwargs: Any,
) -> dict[str, Any]:
```

#### Payload Structure

```mermaid
graph TD
    A[LiteLLM Parameters] --> B[Extract optional_params]
    B --> C[Normalize tools]
    C --> D[Build base payload]
    D --> E[Add model]
    E --> F[Add input messages]
    F --> G[Add instructions]
    G --> H[Add reasoning config]
    H --> I[Add passthrough options]
    I --> J[Final Codex Payload]

    K[model] --> E
    L[messages] --> F
    M[instructions] --> G
    N[reasoning_effort] --> H
    O[metadata, tool_choice] --> I
```

#### Key Payload Fields

| Field | Type | Description | Source |
|-------|------|-------------|---------|
| `model` | `str` | Normalized Codex model identifier | Model mapping |
| `input` | `list[dict]` | Transformed message array | Message conversion |
| `instructions` | `str` | System instructions | Remote resources |
| `tools` | `list[dict]` | Normalized tool definitions | Tool processing |
| `reasoning.effort` | `str` | Reasoning effort level | Config application |
| `text.verbosity` | `str` | Response verbosity | Config application |
| `include` | `list[str]` | Include encrypted reasoning | Constants |
| `stream` | `bool` | Enable streaming | Always `True` |

### Message Transformation

The provider converts OpenAI message format to Codex input format:

```mermaid
graph TD
    A[OpenAI Messages] --> B[Role-based processing]
    B --> C[System messages]
    B --> D[User messages]
    B --> E[Assistant messages]
    B --> F[Tool messages]

    C --> G[Filter toolchain prompts]
    C --> H[Add to instructions]

    D --> I[Convert to Codex format]
    E --> I
    F --> J[Convert to function_call_output]

    I --> K[Codex input array]
    J --> K
    H --> L[Combined instructions]
```

#### Message Type Conversions

| OpenAI Role | Codex Type | Transformation |
|-------------|------------|----------------|
| `system` | `instructions` | Filtered and combined |
| `user` | `message` | Direct conversion |
| `assistant` | `message` | Direct conversion |
| `tool` | `function_call_output` | Special handling |
| `function` | `function_call` | Legacy support |

### Tool Bridge Logic

When tools are present, the provider prepends a special bridge prompt:

```mermaid
sequenceDiagram
    participant C as Client
    participant P as Provider
    participant B as Bridge Logic
    participant T as Tool Processing

    C->>P: completion(model, messages, tools)
    P->>T: _normalize_tools(tools)
    T-->>P: normalized_tools
    alt Tools present
        P->>B: build_tool_bridge_message()
        B-->>P: bridge_message
        P->>P: prepend_bridge(bridge_message)
    end
    P->>P: continue_processing()
```

## Response Processing Details

### Response Type Detection

The provider handles multiple response formats from the Codex backend:

```mermaid
graph TD
    A[HTTP Response] --> B[Check Content-Type]
    B -->|text/event-stream| C[SSE Processing]
    B -->|application/json| D[JSON Processing]

    C --> E[Parse SSE events]
    E --> F[Extract final event]
    F --> G[Convert to JSON]

    D --> H[Direct JSON parse]

    G --> I[Response transformation]
    H --> I
```

### SSE Event Processing

For streaming responses, the provider processes Server-Sent Events:

```python
def convert_sse_to_json(payload: str) -> dict[str, Any]:
    """Convert buffered SSE text to final JSON payload."""
    events = []
    for line in payload.splitlines():
        if not line.startswith("data:"):
            continue
        data = line.removeprefix("data:").strip()
        if not data or data == "[DONE]":
            continue
        try:
            event = json.loads(data)
        except json.JSONDecodeError:
            continue
        if isinstance(event, Mapping):
            events.append(event)

    validated = _extract_validated_response_from_events(events)
    if validated:
        return validated

    return _extract_response_from_events(events)
```

```mermaid
graph TD
    A[SSE Data] --> B[Split by lines]
    B --> C[Extract data: lines]
    C --> D[Parse JSON events]
    D --> E[Filter valid events]
    E --> F[Reverse order]
    F --> G[Find final response]
    G --> H[Extract response payload]
```

### Response Transformation Pipeline

The provider performs complex transformation from Codex format to LiteLLM format:

```mermaid
graph TD
    A[OpenAI Response] --> B[Extract response payload]
    B --> C[Get choices array]
    C --> D{Choices present?}
    D -->|No| E[Check output field]
    D -->|Yes| F[Process primary choice]

    E --> G[Coerce from output]
    G --> F

    F --> H[Extract message]
    H --> I[Collect tool calls]
    I --> J[Resolve content]
    J --> K[Handle function calls]
    K --> L[Build usage]
    L --> M[Create ModelResponse]
```

#### Choice Processing Logic

```mermaid
graph TD
    A[Choice] --> B[Extract message]
    B --> C[Get tool_calls]
    C --> D{Tool calls present?}
    D -->|Yes| E[Extract from message]
    D -->|No| F[Check output field]
    F --> G[Extract function_call items]
    G --> H[Build tool_calls array]

    E --> I[Combine tool calls]
    H --> I

    I --> J[Resolve content]
    J --> K[Set finish_reason]
    K --> L[Final choice]
```

### Tool Call Extraction

The provider handles multiple tool call formats:

```mermaid
graph TD
    A[Response] --> B[Extract tool_calls]
    B --> C{Format detected?}
    C -->|OpenAI format| D[function.name, function.arguments]
    C -->|Codex format| E[name, arguments at top level]
    C -->|Output items| F[type=function_call]

    D --> G[Standardize format]
    E --> G
    F --> G

    G --> H[Build tool_calls array]
    H --> I[Return to transformation]
```

## Authentication Flow Details

### Token Lifecycle Management

```mermaid
sequenceDiagram
    participant P as Provider
    participant A as Auth Module
    participant F as auth.json
    participant C as Cache
    participant O as OpenAI Client

    P->>A: get_auth_context()
    A->>C: Check cached token
    alt Token cached and valid
        C-->>A: cached_token
        A-->>P: AuthContext
    else Token expired/missing
        A->>F: load_auth_data()
        F-->>A: auth_data
        alt Token expired
            A->>O: refresh_token()
            O-->>A: new_token
            A->>F: update auth.json
            A->>C: cache new token
        end
        A-->>P: AuthContext
    end
```

### JWT Account ID Extraction

```mermaid
graph TD
    A[Access Token] --> B[Split JWT]
    B --> C[Extract payload]
    C --> D[Base64 decode]
    D --> E[Parse JSON]
    E --> F[Extract account claim]
    F --> G[Get chatgpt_account_id]
    G --> H[Return account ID]
```

### OpenAI Client Authentication

```mermaid
sequenceDiagram
    participant P as Provider
    participant O as OpenAI Client
    participant T as Token Provider
    participant A as Account ID Provider
    participant H as HTTP Headers

    P->>O: responses.create()
    O->>T: get_bearer_token()
    T-->>O: access_token
    O->>A: get_account_id()
    A-->>O: account_id
    O->>H: inject_custom_headers()
    H->>H: Authorization: Bearer {token}
    H->>H: chatgpt-account-id: {account_id}
    H->>H: OpenAI-Beta: responses=experimental
    O->>Backend: POST /codex/responses
```

## HTTP Dispatch Architecture

### Fallback Mechanism

The provider uses a fallback mechanism when OpenAI client dispatch fails:

```mermaid
graph TD
    A[Request] --> B[Try OpenAI Client]
    B --> C{Success?}
    C -->|Yes| D[Return Response]
    C -->|No| E[Fallback to httpx]
    E --> F[Direct HTTP POST]
    F --> G[Parse Response]
    G --> H[Return Parsed Data]

    B --> I[Log Error]
    I --> J[Sanitize Headers]
    J --> K[Raise Exception]
```

### HTTP Client Configuration

```python
def _create_http_client(base_url: str, timeout: float) -> httpx.Client:
    return httpx.Client(base_url=base_url, timeout=timeout, follow_redirects=True)

def _create_async_http_client(base_url: str, timeout: float) -> httpx.AsyncClient:
    return httpx.AsyncClient(base_url=base_url, timeout=timeout, follow_redirects=True)
```

## Error Handling Strategy

### HTTP Error Processing

```mermaid
graph TD
    A[HTTP Response] --> B[Check status code]
    B -->|2xx| C[Success path]
    B -->|4xx/5xx| D[Error path]

    D --> E[Extract error details]
    E --> F[Parse JSON error]
    F --> G[Extract message]
    G --> H[Add rate limit headers]
    H --> I[Add retry-after info]
    I --> J[Format error string]
    J --> K[Raise RuntimeError]
```

### Network Error Handling

```mermaid
graph TD
    A[Network Request] --> B[HTTPX Client]
    B --> C{Request successful?}
    C -->|Yes| D[Return response]
    C -->|No| E[Handle exception]

    E --> F[HTTPStatusError]
    E --> G[Other exceptions]

    F --> H[Format with response details]
    G --> I[Generic error message]

    H --> J[Raise RuntimeError]
    I --> J
```

## Remote Resources Management

### Instruction Fetching and Caching

```mermaid
graph TD
    A[fetch_codex_instructions] --> B[Get Model Family]
    B --> C[Check Cache]
    C --> D{Cache Valid?}
    D -->|Yes| E[Return Cached]
    D -->|No| F[Fetch from GitHub]
    F --> G[Parse Release]
    G --> H[Download Instructions]
    H --> I[Update Cache]
    I --> E

    C --> J[Load Metadata]
    J --> K[Check TTL]
    K --> L[ETag Support]
```

### Cache Management

```python
@dataclass(slots=True)
class CacheMetadata:
    """Metadata for cached Codex instructions."""
    etag: str | None
    tag: str | None
    last_checked: float | None
    url: str | None

def _should_use_cache(metadata: CacheMetadata, cached: str | None, now: float) -> bool:
    if metadata.last_checked is None or cached is None:
        return False
    return now - float(metadata.last_checked) < constants.CODEX_INSTRUCTIONS_CACHE_TTL_SECONDS
```

## Configuration and Constants

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `CODEX_AUTH_FILE` | `~/.codex/auth.json` | Path to auth file |
| `CODEX_CACHE_DIR` | `~/.opencode/cache` | Instruction cache directory |
| `CODEX_MODE` | `True` | Enable Codex-specific features |
| `CODEX_DEBUG` | `False` | Enable debug logging |

### API Endpoints

| Endpoint | Purpose | Timeout |
|----------|---------|---------|
| `https://chatgpt.com/backend-api/codex/responses` | Main API endpoint | 60s |
| `https://auth.openai.com/oauth/token` | Token refresh | 20s |
| `https://api.github.com/repos/openai/codex/releases/latest` | Get latest release | 20s |

### Model Mapping Constants

```python
MODEL_EFFORT_SUFFIXES = ("none", "minimal", "low", "medium", "high", "xhigh")
BASE_MODELS = ("gpt-5.1-codex", "gpt-5.1-codex-max", "gpt-5.1-codex-mini", "gpt-5.1")
```

## Performance Optimizations

### Caching Strategy

1. **Token Caching**: 5-minute buffer before expiry
2. **Instruction Caching**: 15-minute TTL with ETag support
3. **Model Mapping**: Static dictionary (O(1) lookup)

### Client Optimization

```mermaid
graph TD
    A[HTTP Request] --> B[Reuse OpenAI Client]
    B --> C[Connection pooling]
    C --> D[Keep-alive connections]
    D --> E[Reduced latency]
```

### Response Processing

1. **Typed Model Validation**: OpenAI typed models for reliable parsing
2. **Fallback Mechanisms**: Multiple parsing strategies for robustness
3. **Efficient Transformation**: Pure functions for predictable performance

## Security Considerations

### Token Security

- Tokens stored in user home directory with appropriate permissions
- Memory caching with automatic expiration
- No token logging or persistence beyond necessary

### Request Security

- HTTPS-only communication
- Proper header sanitization
- Input validation for all parameters

### Error Information

- Detailed error messages for debugging
- Rate limit information preservation
- No sensitive data in error responses

## Customization Points

### Custom OpenAI Client

Extend the OpenAI client customization:

```python
class CustomCodexClient(CodexOpenAIClient):
    def _prepare_options(self, options: FinalRequestOptions) -> FinalRequestOptions:
        prepared = super()._prepare_options(options)
        # Add custom headers or modifications
        headers = httpx.Headers(prepared.headers or {})
        headers["Custom-Header"] = "custom-value"
        return prepared.copy(update={"headers": headers})
```

### Custom Response Adapter

Override response transformation:

```python
def custom_transform_response(openai_response: dict[str, Any], model: str) -> ModelResponse:
    # Custom transformation logic
    return transform_response(openai_response, model)
```

### Custom Model Mapping

Extend model normalization:

```python
# Add custom model aliases
alias_bases = {
    "custom-model": "target-base-model",
    # ... more aliases
}
```

This architecture provides a robust, maintainable, and extensible foundation for integrating Codex authentication with OpenAI-compatible APIs while maintaining full compatibility with the LiteLLM ecosystem.
