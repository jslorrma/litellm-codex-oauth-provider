# LiteLLM Codex OAuth Provider

A custom provider for [LiteLLM](https://github.com/BerriAI/litellm) that bridges Codex CLI OAuth authentication to OpenAI-compatible APIs. This enables ChatGPT Plus or Pro access via Codex CLI tokens, with seamless integration into LiteLLM proxy and multi-provider routing.

## Installation

<!-- To be filled in later -->

## Usage

<!-- To be filled in later -->

### Configure LiteLLM

To use the Codex OAuth Provider with LiteLLM, add the following configuration to your `~/.config/litellm/config.yaml` file:

<!-- To be filled in later -->

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

   Using Pixi, install the required dependencies:

   ```bash
   pixi install -e local-dev
   ```

3. **Activate the environment:**

    If you're using `direnv`, simply navigate to the project directory, and it will automatically activate the environment. If not, you can manually activate the Pixi environment:

    ```bash
    pixi shell -e local-dev
    ```

4. **Select Python Interpreter:**

    If you're using VSCode, select the Pixi-managed Python interpreter for the project. You can do this by opening the command palette (`Ctrl+Shift+P` or `Cmd+Shift+P` on Mac) and searching for "Python: Select Interpreter". Choose the interpreter from the  `local-dev` environment at `.pixi/envs/local-dev/bin/python`.

    > Note: If you have the Pixi VSCode extension installed, it may automatically select the correct interpreter for you.

### Pre-commit Hooks (Prek)

- Uses [Prek](https://github.com/j178/prek) for fast, modern git hooks
- Configure hooks in `.pre-commit-config.yaml` (Prek is drop-in compatible)

## License

MIT
