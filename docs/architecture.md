# Architecture Overview

The LiteLLM Codex OAuth Provider is a sophisticated adapter that bridges Codex CLI authentication with OpenAI-compatible APIs. This document provides a comprehensive architectural overview of the system.

## System Architecture

```mermaid
graph TB
    subgraph "Client Applications"
        A[LiteLLM Proxy] --> B[OpenAI Client]
        C[Direct Python Client] --> D[litellm_codex_oauth_provider]
    end

    subgraph "Authentication Layer"
        E[Codex CLI] --> F[~/.codex/auth.json]
        F --> G[AuthContext]
        G --> H[Token Refresh Logic]
    end

    subgraph "Core Provider"
        D --> I[CodexAuthProvider]
        I --> J[Request Builder]
        I --> K[HTTP Transport]
        I --> L[Response Transformer]
    end

    subgraph "External APIs"
        K --> M[ChatGPT Backend API]
        H --> N[OpenAI Auth API]
        O[GitHub API] --> P[Codex Instructions]
    end

    subgraph "Data Flow"
        Q[Model Normalization] --> J
        R[Prompt Derivation] --> J
        S[Tool Bridge Logic] --> J
        T[Reasoning Config] --> J
    end

    style A fill:#e1f5fe
    style D fill:#f3e5f5
    style I fill:#e8f5e8
    style M fill:#fff3e0
    style N fill:#fff3e0
```

## Component Overview

### 1. Authentication Layer (`auth.py`)

The authentication layer manages the complete token lifecycle:

- **Token Extraction**: Reads and validates Codex CLI authentication tokens
- **Account ID Decoding**: Extracts ChatGPT account ID from JWT claims
- **Token Refresh**: Automatically refreshes expired tokens via OpenAI OAuth API
- **Error Handling**: Provides specific exceptions for different auth failure modes

```mermaid
sequenceDiagram
    participant C as Client
    participant P as Provider
    participant A as Auth Module
    participant F as auth.json
    participant O as OpenAI Auth API

    C->>P: completion(model, messages)
    P->>A: get_auth_context()
    A->>F: load_auth_data()
    alt Token Valid
        F-->>A: access_token, expires_at
        A-->>P: AuthContext
    else Token Expired
        F-->>A: expired token
        A->>O: refresh_token()
        O-->>A: new_access_token
        A->>F: update auth.json
        A-->>P: AuthContext
    end
```

### 2. Core Provider (`provider.py`)

The `CodexAuthProvider` class orchestrates the entire request/response pipeline:

#### Request Processing Flow

```mermaid
sequenceDiagram
    participant C as Client
    participant P as CodexAuthProvider
    participant M as Model Mapper
    participant R as Request Builder
    participant H as HTTP Client
    participant T as Response Transformer

    C->>P: completion(model, messages, **kwargs)
    P->>M: normalize_model(model)
    P->>R: build_payload(model, messages, ...)
    R->>R: derive_instructions()
    R->>R: apply_reasoning_config()
    P->>H: POST /codex/responses()
    H-->>P: HTTP Response
    P->>T: transform_response()
    T-->>P: ModelResponse
    P-->>C: ModelResponse
```

#### Key Responsibilities

1. **Model Normalization**: Converts LiteLLM model strings to Codex-compatible identifiers
2. **Request Building**: Constructs Codex API payloads from LiteLLM parameters
3. **HTTP Transport**: Handles network communication with timeout and error handling
4. **Response Transformation**: Converts Codex responses to LiteLLM format
5. **Streaming Support**: Provides both sync and async streaming interfaces

### 3. Model Mapping (`model_map.py`)

Handles intelligent model name normalization and alias resolution:

```mermaid
graph LR
    A[codex/gpt-5.1-codex-low] --> B[strip_provider_prefix]
    B --> C[gpt-5.1-codex-low]
    C --> D[normalize_model]
    D --> E[MODEL_MAP lookup]
    E --> F[gpt-5.1-codex]

    G[codex-oauth/gpt-5-codex-high] --> H[strip_provider_prefix]
    H --> I[gpt-5-codex-high]
    I --> J[normalize_model]
    J --> K[MODEL_MAP lookup]
    K --> L[gpt-5.1-codex]
```

### 4. Prompt Management (`prompts.py`)

Manages dynamic instruction fetching and caching:

```mermaid
graph TD
    A[derive_instructions] --> B{Codex Mode?}
    B -->|Yes| C[get_codex_instructions]
    B -->|No| D[TOOL_REMAP_PROMPT]

    C --> E{Cached?}
    E -->|Yes| F[Return cached]
    E -->|No| G[Fetch from GitHub]
    G --> H[Cache result]
    H --> F

    D --> I[Filter system prompts]
    C --> I
    I --> J[Build final instructions]
    J --> K[Return instructions + messages]
```

### 5. Reasoning Configuration (`reasoning.py`)

Applies model-specific reasoning constraints and effort clamping:

```mermaid
graph TD
    A[apply_reasoning_config] --> B[Extract effort from model]
    B --> C[Extract effort from params]
    C --> D[Determine final effort]
    D --> E[Get model family]
    E --> F[Clamp effort for family]
    F --> G[Apply verbosity settings]
    G --> H[Return config dict]
```

## Data Flow Architecture

### Request Pipeline

```mermaid
flowchart TD
    A[Client Request] --> B[Model String Parsing]
    B --> C[Provider Prefix Stripping]
    C --> D[Model Normalization]
    D --> E[Parameter Validation]
    E --> F[Instruction Derivation]
    F --> G[Payload Construction]
    G --> H[Header Building]
    H --> I[HTTP Request]
    I --> J[Response Processing]
    J --> K[Response Transformation]
    K --> L[LiteLLM Response]
```

### Response Transformation Pipeline

```mermaid
flowchart TD
    A[Codex Response] --> B[Parse JSON]
    B --> C{Response Type?}
    C -->|SSE| D[Extract final event]
    C -->|JSON| E[Direct parse]
    D --> F[Extract choices]
    E --> F
    F --> G[Transform messages]
    G --> H[Handle tool calls]
    H --> I[Build usage stats]
    I --> J[Create ModelResponse]
```

## Security Architecture

### Token Security

```mermaid
graph TD
    A[~/.codex/auth.json] --> B[Encrypted Storage]
    B --> C[Memory Caching]
    C --> D[HTTP Authorization Header]
    D --> E[ChatGPT Backend]

    F[Token Refresh] --> G[OpenAI OAuth API]
    G --> H[New Token]
    H --> I[Update auth.json]
    I --> J[Clear Memory Cache]
```

### Error Handling Strategy

```mermaid
graph TD
    A[Network Error] --> B[HTTP Status Check]
    B -->|4xx| C[Client Error Mapping]
    B -->|5xx| D[Server Error Mapping]
    C --> E[RuntimeError with details]
    D --> E
    F[Auth Error] --> G[Specific Exception Types]
    G --> H[Token Refresh Attempt]
    H --> I{Fresh Token?}
    I -->|Yes| J[Retry Request]
    I -->|No| K[Raise Auth Error]
```

## Configuration Architecture

### Environment Variables

```mermaid
graph LR
    A[CODEX_AUTH_FILE] --> B[Auth File Path]
    C[CODEX_CACHE_DIR] --> D[Cache Directory]
    E[CODEX_MODE] --> F[Feature Flags]

    B --> G[AuthContext Loading]
    D --> H[Instruction Caching]
    F --> I[Tool Bridge Logic]
```

### Model Configuration

```mermaid
graph TD
    A[Model String] --> B[Prefix Detection]
    B --> C[Alias Resolution]
    C --> D[Effort Extraction]
    D --> E[Family Classification]
    E --> F[Normalization Rules]
    F --> G[Final Model ID]
```

## Performance Considerations

### Caching Strategy

1. **Token Caching**: In-memory cache with 5-minute buffer
2. **Instruction Caching**: File-based cache with 15-minute TTL
3. **Model Mapping**: Static dictionary lookup (O(1))

### Network Optimization

1. **Connection Pooling**: httpx client reuse
2. **Timeout Management**: 60s request timeout, 20s GitHub timeout
3. **Retry Logic**: Automatic token refresh on auth failures

## Extension Points

### Custom Model Support

The system supports custom model additions through the `MODEL_MAP` in `model_map.py`:

```python
# Add custom model aliases
alias_bases = {
    "custom-model": "target-base-model",
    # ... more aliases
}
```

### Custom Prompt Logic

Extend `derive_instructions()` in `prompts.py` to add custom instruction logic:

```python
def derive_instructions(messages, *, codex_mode, normalized_model):
    # Custom logic here
    return instructions, filtered_messages
```

### Custom Response Transformation

Override or extend `_transform_response()` in `provider.py` for custom response handling:

```python
def _transform_response(self, openai_response: dict[str, Any], model: str) -> ModelResponse:
    # Custom transformation logic
    return transformed_response
```
