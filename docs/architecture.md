# Architecture Overview

The LiteLLM Codex OAuth Provider is a sophisticated adapter that bridges Codex CLI authentication with OpenAI-compatible APIs through a modern architecture using the official OpenAI client library. This document provides a comprehensive architectural overview of the system.

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
        I --> J[OpenAI Client Delegation]
        I --> K[Request Orchestration]
        I --> L[Response Adapter]
    end

    subgraph "OpenAI Client Layer"
        J --> M[CodexOpenAIClient]
        J --> N[AsyncCodexOpenAIClient]
        M --> O[Custom Auth Headers]
        N --> O
        O --> P[Token Provider Pattern]
    end

    subgraph "Response Processing"
        L --> Q[Response Adapter]
        Q --> R[OpenAI Typed Models]
        Q --> S[SSE Processing]
        Q --> T[Fallback Mechanisms]
    end

    subgraph "External APIs"
        M --> U[ChatGPT Backend API]
        N --> U
        H --> V[OpenAI Auth API]
        W[GitHub API] --> X[Codex Instructions]
    end

    subgraph "Data Flow"
        Y[Model Normalization] --> K
        Z[Prompt Derivation] --> K
        AA[Tool Bridge Logic] --> K
        BB[Reasoning Config] --> K
    end

    style A fill:#e1f5fe
    style D fill:#f3e5f5
    style I fill:#e8f5e8
    style M fill:#fff3e0
    style N fill:#fff3e0
    style U fill:#fff3e0
    style V fill:#fff3e0
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

### 2. OpenAI Client Integration (`openai_client.py`)

The OpenAI client layer provides Codex-specific customization of the official OpenAI client:

#### Custom Client Architecture

```mermaid
graph TD
    A[CodexAuthProvider] --> B[CodexOpenAIClient]
    A --> C[AsyncCodexOpenAIClient]

    B --> D[_BaseCodexClient]
    C --> E[AsyncOpenAI]

    D --> F[Custom Auth Headers]
    E --> G[Custom Auth Headers]

    F --> H[Token Provider]
    G --> H
    H --> I[Account ID Provider]

    D --> J[Header Injection]
    E --> J
    J --> K[OpenAI Beta Headers]
    J --> L[Content-Type Headers]
    J --> M[Accept Headers]
```

#### Key Customizations

1. **Token Provider Pattern**: Dynamic token retrieval from provider
2. **Custom Header Injection**: Codex-specific headers added to all requests
3. **Account ID Resolution**: Automatic ChatGPT account ID injection
4. **Beta Feature Headers**: Required OpenAI beta headers for Codex API

```python
# Custom header injection example
headers = httpx.Headers(prepared.headers or {})
headers["Authorization"] = f"Bearer {token}"
headers.setdefault("OpenAI-Beta", "responses=experimental")
headers.setdefault("originator", "codex_cli_rs")
headers.setdefault("Content-Type", "application/json")
headers["Accept"] = "text/event-stream"
if account_id:
    headers.setdefault("chatgpt-account-id", account_id)
```

### 3. Core Provider (`provider.py`)

The `CodexAuthProvider` class orchestrates the entire request/response pipeline:

#### Request Processing Flow

```mermaid
sequenceDiagram
    participant C as Client
    participant P as CodexAuthProvider
    participant M as Model Mapper
    participant O as OpenAI Client
    participant A as Response Adapter

    C->>P: completion(model, messages, **kwargs)
    P->>M: normalize_model(model)
    P->>P: derive_instructions()
    P->>P: apply_reasoning_config()
    P->>O: responses.create()
    O-->>P: OpenAI Response
    P->>A: transform_response()
    A-->>P: ModelResponse
    P-->>C: ModelResponse
```

#### Key Responsibilities

1. **Model Normalization**: Converts LiteLLM model strings to Codex-compatible identifiers
2. **Request Orchestration**: Coordinates between OpenAI client and response adapter
3. **Client Delegation**: Manages sync/async OpenAI client instances
4. **Configuration Resolution**: Handles base URL and mode detection

### 4. Response Adapter (`adapter.py`)

The response adapter provides pure functions for transforming Codex responses to LiteLLM format:

#### Response Transformation Pipeline

```mermaid
graph TD
    A[OpenAI Response] --> B[Parse Response Body]
    B --> C{Response Type?}
    C -->|SSE| D[Convert SSE to JSON]
    C -->|JSON| E[Direct Parse]
    C -->|Typed| F[OpenAI Typed Models]

    D --> G[Extract Response Payload]
    E --> G
    F --> G

    G --> H[Transform Choices]
    H --> I[Handle Tool Calls]
    I --> J[Resolve Content]
    J --> K[Build Usage]
    K --> L[Create ModelResponse]
```

#### Key Features

1. **OpenAI Typed Models**: Uses official OpenAI response models for validation
2. **SSE Processing**: Handles Server-Sent Events with fallback mechanisms
3. **Flexible Parsing**: Multiple parsing strategies for different response formats
4. **Tool Call Extraction**: Comprehensive tool call handling from various formats

### 5. Remote Resources (`remote_resources.py`)

Manages dynamic instruction fetching and caching:

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

### 6. Model Mapping (`model_map.py`)

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
    G --> H[OpenAI Client Delegation]
    H --> I[Custom Header Injection]
    I --> J[HTTP Request]
    J --> K[Response Processing]
    K --> L[Response Transformation]
    L --> M[LiteLLM Response]
```

### Response Transformation Pipeline

```mermaid
flowchart TD
    A[OpenAI Response] --> B[Response Body Parsing]
    B --> C{Format Detection}
    C -->|SSE| D[SSE to JSON Conversion]
    C -->|JSON| E[Direct JSON Parse]
    C -->|Typed| F[OpenAI Model Validation]

    D --> G[Extract Response Payload]
    E --> G
    F --> G

    G --> H[Choice Processing]
    H --> I[Tool Call Extraction]
    I --> J[Message Content Resolution]
    J --> K[Usage Statistics]
    K --> L[ModelResponse Construction]
```

## Security Architecture

### Token Security

```mermaid
graph TD
    A[~/.codex/auth.json] --> B[Encrypted Storage]
    B --> C[Token Provider Pattern]
    C --> D[Dynamic Token Retrieval]
    D --> E[Custom Header Injection]
    E --> F[OpenAI Client]
    F --> G[ChatGPT Backend]

    H[Token Refresh] --> I[OpenAI OAuth API]
    I --> J[New Token]
    J --> K[Update auth.json]
    K --> L[Clear Memory Cache]
```

### Authentication Flow

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

## Configuration Architecture

### Environment Variables

```mermaid
graph LR
    A[CODEX_AUTH_FILE] --> B[Auth File Path]
    C[CODEX_CACHE_DIR] --> D[Cache Directory]
    E[CODEX_MODE] --> F[Feature Flags]
    G[CODEX_DEBUG] --> H[Debug Logging]

    B --> I[AuthContext Loading]
    D --> J[Instruction Caching]
    F --> K[Tool Bridge Logic]
    H --> L[Logging Configuration]
```

### Client Configuration

```mermaid
graph TD
    A[CodexAuthProvider] --> B[Initialize Clients]
    B --> C[CodexOpenAIClient]
    B --> D[AsyncCodexOpenAIClient]

    C --> E[Token Provider]
    C --> F[Account ID Provider]
    C --> G[Base URL]
    C --> H[Timeout]

    D --> E
    D --> F
    D --> G
    D --> H

    E --> I[get_bearer_token]
    F --> J[_resolve_account_id]
    G --> K[_resolve_base_url]
    H --> L[60.0 seconds]
```

## Performance Considerations

### Caching Strategy

1. **Token Caching**: In-memory cache with 5-minute buffer
2. **Instruction Caching**: File-based cache with 15-minute TTL and ETag support
3. **Model Mapping**: Static dictionary lookup (O(1))

### Client Optimization

1. **Connection Reuse**: OpenAI client manages connection pooling
2. **Timeout Management**: 60s request timeout, 20s GitHub timeout
3. **Async Support**: Full async/await support for concurrent requests

### Response Processing

1. **Typed Model Validation**: OpenAI typed models for reliable parsing
2. **Fallback Mechanisms**: Multiple parsing strategies for robustness
3. **Efficient Transformation**: Pure functions for predictable performance

## Extension Points

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

## Migration from Previous Architecture

### Key Changes

1. **HTTP Transport**: Replaced direct httpx with OpenAI client library
2. **Response Handling**: Extracted to separate adapter module
3. **Authentication**: Token provider pattern for dynamic token retrieval
4. **Error Handling**: OpenAI typed models with comprehensive fallbacks
5. **Simplification**: Removed Cloudflare workarounds and browser emulation

### Benefits

1. **Better Reliability**: Official OpenAI client with proven stability
2. **Improved Maintainability**: Clear separation of concerns
3. **Enhanced Testability**: Pure functions and dependency injection
4. **Future Compatibility**: Aligned with OpenAI ecosystem evolution

This architecture provides a robust, maintainable, and extensible foundation for integrating Codex authentication with OpenAI-compatible APIs while maintaining full compatibility with the LiteLLM ecosystem.
