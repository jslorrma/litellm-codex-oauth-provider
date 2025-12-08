# LiteLLM Codex OAuth Provider

A custom provider for [LiteLLM](https://github.com/BerriAI/litellm) that bridges Codex CLI OAuth authentication to OpenAI-compatible APIs. This enables ChatGPT Plus or Pro access via Codex CLI tokens, with seamless integration into LiteLLM proxy and multi-provider routing.

## Installation

### Prerequisites

1. **Codex CLI**: Install and authenticate with the Codex CLI:

    ```bash
    # Install Codex CLI (if not already installed)
    # Follow instructions at https://github.com/openai/codex

    # Authenticate with your ChatGPT Plus account
    codex login

    # Verify authentication
    codex login status
    ```

    The above command should create `~/.codex/auth.json` containing your OAuth tokens, which the provider will use to access OpenAI services. If you face issues, refer to the [Codex CLI documentation](https://github.com/openai/codex).

2. **LiteLLM**: Ensure LiteLLM is installed with proxy support:

    > [!NOTE]
    > Only if litellm CLI should be used. If docker-compose is used, the image already includes LiteLLM with proxy support and this step can be skipped.

    ```bash
    uv pip install 'litellm[proxy]'
    ```

### Installation

Install the `litellm-codex-oauth-provider` package via uv:

```bash
uv pip install litellm-codex-oauth-provider
```

> [!IMPORTANT]
> Ensure that the `litellm-codex-oauth-provider` package is installed in the same environment where LiteLLM is running.

## Usage

LiteLLM can use the Codex OAuth provider either directly in Python code or via the LiteLLM proxy (CLI or Docker). Below are instructions for all three methods.

> [!TIP]
> For more details, including additional proxy options and links to the official LiteLLM docs, see [`Usage` document](docs/usage.md).

### Direct Usage (Python)

```python
import litellm
from litellm_codex_oauth_provider import codex_auth_provider

# Register the custom provider
litellm.custom_provider_map = [
    {"provider": "codex", "custom_handler": CodexAuthProvider}
]

# Use with LiteLLM
response = litellm.completion(
    model="codex/gpt-5.1-codex-max",
    messages=[
        {"role": "user", "content": "Write a Python function to reverse a string"}
    ],
    temperature=0.7,
    max_tokens=500
)

print(response.choices[0].message.content)
```

### Via LiteLLM Proxy

CLI or Docker can be used to run a LiteLLM proxy that routes requests to the Codex OAuth provider. Both methods require similar configuration.

1. **Create a LiteLLM configuration file** (`config.yaml`):

```yaml
# ============================================
# LITELLM CONFIG WITH CODEX OAUTH PROVIDER
# ============================================

general_settings:
  master_key: sk-your-master-key-12345

# ============================================
# MODEL CONFIGURATIONS
# ============================================
model_list:

  # CHATGPT PLUS via Codex OAuth (Your custom provider)
  - model_name: chatgpt-plus-gpt-5.1-codex-max
    litellm_params:
      model: codex/gpt-5.1-codex-max
      # No API key needed - uses Codex auth.json

  - model_name: chatgpt-plus-gpt-5.1-codex
    litellm_params:
      model: codex/gpt-5.1-codex

  - model_name: chatgpt-plus-gpt-5.1
    litellm_params:
      model: codex/gpt-5.1

# ============================================
# CUSTOM PROVIDER REGISTRATION
# ============================================
litellm_settings:
  custom_provider_map:
    - provider: "codex"
      custom_handler: litellm_codex_oauth_provider.provider.codex_auth_provider
```

2. **Start the LiteLLM proxy via CLI**:

To start the LiteLLM proxy with the above configuration on port `4000`, run:

```bash
litellm --config config.yaml --port 4000
```

> [!TIP]
> You can also use `uvx` to run the LiteLLM proxy if you have installed LiteLLM via uv, like so:
>
> ```bash
> uvx --with litellm-codex-oauth-provider --with 'litellm[proxy]' litellm --config config.yaml --port 4000
> ```

3. **Make API requests**:

Test the setup by making a request to the LiteLLM proxy:

```bash
curl -X POST http://localhost:4000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer sk-your-master-key-12345" \
  -d '{
    "model": "chatgpt-plus-gpt-5.1-codex-max",
    "messages": [{"role": "user", "content": "Ping!"}]
  }'
```

### Docker Deployment

A sample `docker-compose.yml` is provided for easy deployment. Make sure to adjust environment variables as needed.

To start the LiteLLM proxy with Docker, run:

```bash
docker-compose up -d
```

---

## Development & Contribution

This project uses `pixi` and `direnv` for managing development environments and automating setup tasks, but `direnv` is optional and you can also manually set up the environment using `pixi`. Follow the instructions below to get started.

<details><summary>Install Pixi and Direnv</summary>

### Install Pixi

Follow the official [Pixi installation guide](https://pixi.sh/latest/#installation) to install Pixi on your system.

> Pixi also has a [VSCode extension](https://marketplace.visualstudio.com/items?itemName=jjjermiah.pixi-vscode) for automatic environment management within the editor.

### Install Direnv (Optional)

Direnv is optional but recommended for automatic environment activation. Follow the official [Direnv installation guide](https://direnv.net/docs/installation.html) to install Direnv on your system.

If you're using `direnv`, make sure to allow the environment when you first enter the project directory:

```bash
direnv allow
```

> To use Direnv with VSCode, consider installing the [Direnv extension](https://marketplace.visualstudio.com/items?itemName=Rubymaniac.vscode-direnv) for seamless integration.

</details>

### Development Environment Setup

This project uses `pixi` to manage a consistent development environment. To set up the environment, follow these steps:

1. **Clone the repository:**

   ```bash
   git clone <your-repository-url>
   cd litellm-codex-oauth-provider
   ```

2. **Install dependencies:**

   Using Pixi, install the required dependencies and set up the local development environment:

   ```bash
   pixi install -e local-dev
   pixi run post-install
   ```

3. **Activate the environment:**

    If you're using `direnv`, simply navigate to the project directory, and it will automatically activate the environment. If not, you can manually activate the Pixi environment:

    ```bash
    pixi shell -e local-dev
    ```

4. **Select Python Interpreter:**

    If you're using VSCode, select the Pixi-managed Python interpreter for the project. You can do this by opening the command palette (`Ctrl+Shift+P` or `Cmd+Shift+P` on Mac) and searching for "Python: Select Interpreter". Choose the interpreter from the  `local-dev` environment at `.pixi/envs/local-dev/bin/python`.

    > [!NOTE]
    > If you have the Pixi VSCode extension installed, it may automatically select the correct interpreter for you.

### Pre-commit Hooks (Prek)

- Uses [Prek](https://github.com/j178/prek) for fast, modern git hooks
- Configure hooks in `.pre-commit-config.yaml` (Prek is drop-in compatible)
