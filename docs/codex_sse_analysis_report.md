# Codex SSE Dump Analysis & Refactoring Report

## 1. Request Payload Structure

The payload sent to the Codex API (`gpt-5.1-codex-max`) mirrors the OpenAI Chat Completion structure but includes several Codex-specific extensions.

### Key Fields

- `model`: "gpt-5.1-codex-max"
- `input`: Standard OpenAI messages array.
  - `{"type": "message", "content": "...", "role": "user"}`
- `instructions`: **Critical Extension**. A massive markdown block defining:
  - CLI environment rules (`rg` over `grep`).
  - Editing constraints (ASCII, brief comments).
  - Git handling (never revert user changes).
  - Sandboxing & permissions (`sandbox_mode`, `approval_policy`).
  - Output formatting guidelines.
- `include`: `["reasoning.encrypted_content"]` - Explicitly requesting reasoning data.
- `stream`: `true` - Activates SSE streaming.
- `reasoning`:
  - `effort`: "medium"
  - `summary`: "auto"
- `text`:
  - `verbosity`: "medium"

## 2. SSE Response Structure & Types

The SSE stream is highly structured and granular, breaking down the response into distinct "items" (reasoning vs. content) and "parts" (summaries vs. text deltas).

### Event Types Hierachy

1. **Lifecycle Events**:
    - `response.created`: Initial metadata.
    - `response.in_progress`: Status update.
    - `response.completed`: Final wrap-up.

2. **Item Lifecycle (Reasoning & Content)**:
    - `response.output_item.added`: Starts a new item (e.g., a reasoning block or a message).
    - `response.output_item.done`: Finishes an item.

3. **Content Part Lifecycle**:
    - `response.content_part.added` / `response.reasoning_summary_part.added`: Starts a specific part within an item.
    - `response.content_part.done` / `response.reasoning_summary_part.done`: Finishes a part.

4. **Deltas (The Streaming Payload)**:
    - `response.reasoning_summary_text.delta`: Text chunks for the reasoning summary.
    - `response.output_text.delta`: Text chunks for the actual assistant reply.

### Critical ID Mapping

- **Items** have distinct IDs (e.g., `rs_...` for reasoning, `msg_...` for messages).
- **Deltas** reference these IDs via `item_id`. This allows multiplexing, though in this dump, they appear sequential.

## 3. Parsing Strategy

To correctly parse and merge this stream into a standard OpenAI-compatible format, the parser must track state across these events.

### State Machine Requirements

1. **Item Tracking**: Maintain a map of `item_id` -> `current_content`.
2. **Type Discrimination**:
    - If `item.type == "reasoning"`: Accumulate deltas into a reasoning field (or ignore if encrypted content is handled separately). Note the explicit `response.reasoning_summary_text.delta` events.
    - If `item.type == "message"`: Accumulate `response.output_text.delta` into the main content buffer.
3. **Delta merging**:
    - Concatenate `delta` fields from `*.delta` events.
    - Ignore `obfuscation` fields (likely internal debug/safety data).

### Mapping to OpenAI/LiteLLM Format

- **Reasoning**: The `response.reasoning_summary_text.delta` events should ideally map to a reasoning field in the final response if supported, or be logged/discarded depending on the API contract.
- **Content**: The `response.output_text.delta` events directly map to the standard `choices[0].delta.content` in an OpenAI streaming chunk.

## 4. Refactoring Recommendations

Based on this analysis, the current `sse_utils.py` and `provider.py` likely need to be robust against this granular event structure.

1. **Event Normalizer Upgrade**: The `normalize_sse_event` function must handle `response.*` event types, not just standard OpenAI `text.delta`.
    - Map `response.output_text.delta` -> `text_delta` (standard internal type).
    - Map `response.reasoning_summary_text.delta` -> `reasoning_delta` (new internal type).
    - Map `response.output_item.done` / `response.completed` -> `done` (standard internal type).

2. **Streaming Utils Update**:
    - `build_text_chunk`: Should accept `text_delta` from the normalizer.
    - **New**: `build_reasoning_chunk`: To stream reasoning back to the user if the client supports it (e.g., via a specific field or concatenated to content with a separator).

3. **Testing**:
    - The mock generator (`MockSSEGenerator`) currently simulates a simpler format. It should be updated to optionally produce this complex `response.*` structure to verify the parser's resilience against real Codex output.

This structure proves that the Codex API is significantly more complex than a standard OpenAI backend, necessitating a specialized adapter layer that this project provides.
