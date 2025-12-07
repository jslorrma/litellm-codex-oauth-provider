<!-- markdownlint-disable MD046 -->
<!-- markdownlint-disable-next-line MD041 -->
## Using the Codex OAuth Provider with LiteLLM Proxy

This guide walks you through running LiteLLM Proxy with the Codex OAuth provider. It explains the
moving parts, provides copy-pasteable configs, and points to the official LiteLLM docs for deeper
features such as routing, observability, and spend controls.

### What this does (and why)

- You keep using OpenAI-format requests, but LiteLLM forwards them to ChatGPT Plus via your Codex
  CLI auth.
- All LiteLLM proxy features still apply: routing/fallbacks, logging callbacks, cost tracking, and
  rate limits (see https://docs.litellm.ai/docs/ for details).

### Prerequisites

- Codex CLI logged in: run `codex login` and confirm `~/.codex/auth.json` exists.
- Package importable in the runtime (host or container).
- LiteLLM available (`uv pip install 'litellm[proxy]'` if you only need the proxy binary).
- Network egress to `chatgpt.com` (the Codex backend) and `auth.openai.com` for token refresh.

### How the provider is registered

LiteLLM needs two pieces of information:

- `provider`: the prefix used in model strings (`codex-oauth/<openai-model>`).
- `custom_handler`: the import path to the handler class.

For this project:

```yaml
litellm_settings:
  custom_provider_map:
    - provider: codex-oauth
      custom_handler: litellm_codex_oauth_provider.provider.CodexAuthProvider
```

### A single config for CLI or Docker

Create `config.yaml` (adjust the model names to your preference):

```yaml
general_settings:
  master_key: sk-your-master-key-12345

model_list:
  - model_name: chatgpt-plus-gpt-5.1-codex-max
    litellm_params:
      model: codex-oauth/gpt-5.1-codex-max

litellm_settings:
  custom_provider_map:
    - provider: codex-oauth
      custom_handler: litellm_codex_oauth_provider.provider.CodexAuthProvider
```

- `master_key`: the key clients use to talk to your proxy.
- `model_name`: the alias clients will request.
- `litellm_params.model`: the actual provider/model string (`codex-oauth/<openai-model>`).
- `custom_provider_map`: where LiteLLM learns how to load the handler.

### Run with the LiteLLM CLI

Start the proxy:

```bash
PYTHONPATH=$PWD litellm --config config.yaml --port 4000
```

Smoke-test with curl:

```bash
curl -X POST http://localhost:4000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer sk-your-master-key-12345" \
  -d '{
    "model": "chatgpt-plus-gpt-5.1-codex-max",
    "messages": [{"role": "user", "content": "Ping!"}]
  }'
```

You can also use the OpenAI client by pointing `base_url` to the proxy and supplying the
`master_key` as the API key.

### Run with Docker Compose

```yaml
version: '3.8'

services:
  litellm-proxy:
    image: ghcr.io/berriai/litellm:main-latest
    container_name: litellm-codex-proxy
    ports:
      - "4000:4000"
    volumes:
      - ./config.yaml:/app/config.yaml:ro
      - ~/.codex:/root/.codex:ro  # Codex tokens (read-only, required)
      # Optional: mount the package if developing locally
      # - ./:/app
    environment:
      - PYTHONPATH=/app
      - LITELLM_LOG=INFO
    command: ["--config", "/app/config.yaml"]
    restart: unless-stopped
```

Launch it:

```bash
docker-compose up -d
```

Then reuse the curl command above to verify responses.

### Tips, options, and references

- **Model naming**: always prefix with `codex-oauth/` (e.g., `codex-oauth/gpt-5.1-codex-max`), and
  set that in `litellm_params.model`.
- **Token location**: default is `~/.codex/auth.json`. Keep that path mounted. If you must relocate
  it, adjust `litellm_codex_oauth_provider.constants.DEFAULT_CODEX_AUTH_FILE` (or symlink the
  file).
- **Logging and callbacks**: use LiteLLM’s knobs (`LITELLM_LOG`, callbacks, observability hooks) as
  described in the official docs.
- **Exception handling**: LiteLLM maps provider errors to OpenAI-style exceptions, so existing
  OpenAI error handling generally works as-is.
- **Streaming**: set `stream: true` in requests; responses follow the OpenAI stream chunk format.
- **Deeper LiteLLM features**: routing/fallbacks, spend controls, and request transformation
  endpoints are documented at https://docs.litellm.ai/docs/.

### Quick verification checklist

- Codex CLI login succeeded and `~/.codex/auth.json` is mounted/visible.
- `custom_provider_map` includes `codex-oauth` with the handler path above.
- `model_list` entries point to `codex-oauth/<model>` and are referenced by `model_name`.
