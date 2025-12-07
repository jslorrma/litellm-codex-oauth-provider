# Codex API Integration Details

This document provides comprehensive details about how the provider wraps the Codex backend API, including request/response handling, authentication flow, and internal processing details.

## Codex Backend API Overview

The provider acts as a sophisticated adapter between LiteLLM's OpenAI-compatible interface and the ChatGPT backend API. It handles the complete request/response lifecycle while maintaining compatibility with both systems.

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
    O[temperature, max_tokens] --> I
```

#### Key Payload Fields

| Field | Type | Description | Source |
|-------|------|-------------|---------|
| `model` | `str` | Normalized Codex model identifier | Model mapping |
| `input` | `list[dict]` | Transformed message array | Message conversion |
| `instructions` | `str` | System instructions | Prompt derivation |
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
@staticmethod
def _convert_sse_to_json(payload: str) -> dict[str, Any]:
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

    return CodexAuthProvider._extract_response_from_events(events)
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
    A[Codex Response] --> B[Extract response payload]
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
    participant O as OpenAI Auth API

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

## Configuration and Constants

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `CODEX_AUTH_FILE` | `~/.codex/auth.json` | Path to auth file |
| `CODEX_CACHE_DIR` | `~/.opencode/cache` | Instruction cache directory |
| `CODEX_MODE` | `True` | Enable Codex-specific features |

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

### Connection Management

```mermaid
graph TD
    A[HTTP Request] --> B[Reuse httpx Client]
    B --> C[Connection pooling]
    C --> D[Keep-alive connections]
    D --> E[Reduced latency]
```

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
