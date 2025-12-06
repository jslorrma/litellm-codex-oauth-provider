<!-- markdownlint-disable MD046 -->
<!-- markdownlint-disable-next-line MD041 -->
## Getting Started

This guide helps you get productive after you have completed the [installation](installation.md). It covers the project structure, development workflow, Pixi environments, adding dependencies, running tasks, and more.

## Project Structure

The project contains Python modules in the `src/litellm_codex_oauth_provider` directory and corresponding tests in the `tests` directory. All configuration is managed through the `pyproject.toml` file, which defines dependencies, development tools, features, environments, and automated tasks.

??? info "Project Structure"

    | File / Directory            | Purpose                                                                  |
    | --------------------------- | ------------------------------------------------------------------------ |
    | `.github`                   | CI/CD workflow definitions and a PR template                             |
    | `src/litellm_codex_oauth_provider` | Project import modules                                                   |
    | `tests`                     | Unit, integration, and end-to-end tests                                  |
    | `docs`                      | Project documentation, including guides and API reference                |
    | `pyproject.toml`            | Main project configuration file for Pixi, Ruff, and other tools          |
    | `.pre-commit-config.yaml`   | Configuration for pre-commit hooks, managed by Prek                      |
    | `pixi.lock`                 | Lockfile for reproducible environments                                   |
    | `README.md`                 | General project overview, displayed when visiting the GitHub repository  |

## Pixi Environments and Features

Pixi uses **features** to group related dependencies (e.g. test, lint, docs, build, local-dev). **Environments** are installable sets that combine one or more features. This allows you to install only what you need for a specific workflow.

| Environment      | Included Features                | Purpose                                                      | When to Use                          |
|------------------|----------------------------------|--------------------------------------------------------------|--------------------------------------|
| default          | (none, just runtime deps)        | Basic runtime dependencies                                   | Minimal installation for running code |
| local-dev        | test, lint, pre-commit, local    | Complete development setup (recommended)                     | Main development work                |
| test             | test                             | Testing dependencies (pytest, coverage, etc.)                | Running tests only                   |
| lint             | lint                             | Code formatting and linting tools                            | Code quality checks only             |
| pre-commit       | pre-commit                       | Pre-commit hooks and code quality checks                     | Setting up git hooks                 |
| docs             | docs                             | Documentation generation and publishing                      | Building documentation               |
| build            | build                            | Package building and publishing                              | Creating releases                    |

- **Features** are defined in `[tool.pixi.feature.<feature>]` sections in `pyproject.toml`.
- **Environments** are defined in `[tool.pixi.environments]` and list which features they include.
- You can customize environments and features in `pyproject.toml` as needed.

## Adding Dependencies

When you need to add a new package to the project, choose the right type:

- **Runtime dependencies** (should always be added from PyPI for consistent wheels):

  ```bash
  pixi add --pypi <package-name>
  ```

- **Feature/development dependencies** (for a specific feature/environment):

  ```bash
  pixi add -f <feature-name> <package-name>
  ```

- **PyPI-only packages**:

  ```bash
  pixi add -f <feature-name> <package-name> --pypi
  ```

After adding dependencies, they will be automatically installed in the relevant environments.

## Development Workflow

The combination of Pixi and (optionally) Direnv provides an automated development workflow:

1. **Enter the project directory**. If using `direnv`, the environment activates automatically. If not, run `pixi shell`.
2. **Make your changes** - Edit code, add tests, update documentation.
3. **Run tasks** - Use `pixi run <task>` to test, lint, format, or build.
4. **Commit** - Pre-commit hooks automatically run quality checks.

See [CONTRIBUTING.md](../CONTRIBUTING.md) for contribution policy, code style, and PR workflow.

### Available Development Tasks

All development tasks are predefined and can be run with `pixi run <task>`:

| Task                  | Purpose                                              | Environment |
|-----------------------|------------------------------------------------------|-------------|
| test                  | Run all tests with pytest                           | test        |
| test-with-coverage    | Run tests and generate coverage reports             | test        |
| lint                  | Run Ruff linter and auto-fix issues                 | lint        |
| format                | Format code using Ruff formatter                    | lint        |
| docs-build            | Build documentation with MkDocs                     | docs        |
| docs-serve            | Serve documentation locally with live reload        | docs        |
| run-prek              | Run all pre-commit hooks on all files               | pre-commit  |
| install-prek          | Install pre-commit hooks                            | pre-commit  |
| requirements-export   | Export runtime requirements to requirements.txt     | default     |
| requirements-export-dev| Export dev requirements to requirements-dev.txt    | local-dev   |

### Common Development Commands

**Run tests:**

```bash
pixi run test
```

**Format and lint your code:**

```bash
pixi run format
pixi run lint
```

**Build and serve documentation locally:**

```bash
pixi run -e docs docs-serve
```

**Export requirements for other platforms:**

```bash
pixi run requirements-export
```

### Working with VS Code

This project is preconfigured for VS Code with the following features:

- **Test Explorer Integration** - VS Code's test explorer is automatically configured in `.vscode/settings.json`.
- **Python Interpreter** - Automatically detects the Pixi-managed Python environment (especially with the Pixi VSCode extension).
- **Linting and Formatting** - Ruff is configured for real-time code quality feedback.

**Tip:** Open the "Testing" tab in VS Code to see all available tests and run them with one click.

### Documentation Workflow

The documentation is built using MkDocs with Material theme.

**Build documentation locally:**

```bash
pixi run -e docs docs-build
```

**Serve documentation with live reload:**

```bash
pixi run -e docs docs-serve
```

The documentation includes:

- Getting Started guide
- API reference (auto-generated)
- Changelog
- Contributing guidelines

### Publishing and Release Workflow

**Create a new release:**

1. Bump the version:

   ```bash
   pixi run -e build bump-version [patch|minor|major]
   ```
   This updates the project version following [semantic versioning](https://semver.org/) and automatically commits the changes.

2. Build the package:

   ```bash
   pixi run -e build build
   ```

The CI/CD pipeline will automatically build and publish the package when you push a new version tag.

## Git Hooks

We use [`prek`][prek] to run git hooks, helping you develop high-quality code. The hooks are configured in the `.pre-commit-config.yaml` file and executed before each commit.

For instance, [`ruff`][ruff] & [`ruff-format`][ruff-format] fix the code base in-place to adhere to reasonable coding standards. `mypy` and `ruff` lint the code for correctness. These tools are configured via `pyproject.toml` and `.pre-commit-config.yaml`.

!!! info "Installation"

    The hooks are installed automatically when you run `pixi install` or `pixi run post-install`. You can also install them manually:

    ```bash
    pixi run -e pre-commit install-prek
    ```

??? example "Available pre-commit hooks"
    {% raw %}
    ```yaml
    -   repo: https://github.com/astral-sh/ruff-pre-commit
        rev: v0.5.5
        hooks:
            - id: ruff
            - id: ruff-format
    ```
    {% endraw %}

## CI/CD Pipelines

This project uses GitHub Actions for continuous integration. The pipeline workflows are located in the `.github/workflows` directory.

### CI Pipeline Overview

The CI pipeline runs on every push and pull request and includes the following jobs:

| Job         | Purpose                                                      |
|-------------|--------------------------------------------------------------|
| lint        | Lint and format codebase using Ruff and Pixi                 |
| test        | Run tests and upload coverage reports                        |
| build       | Build the Python package (wheel)                             |

- **Linting:** Uses `pixi run -e lint lint` and `pixi run -e lint format` for code quality.
- **Testing:** Uses `pixi run -e test test-with-coverage` and publishes test and coverage results.
- **Build:** Uses `pixi run -e build build` to create wheel distributions.

### How to Trigger and Interpret Pipeline Results

- Pipelines are triggered automatically on branch updates and PRs.
- Results are visible in the "Actions" tab of the GitHub repository.
- Lint, test, and build results are available as pipeline artifacts and summary reports.

For more details, see the pipeline YAML files and the [Pixi documentation](https://pixi.sh/docs/).

[prek]: https://github.com/j178/prek
[ruff]: https://docs.astral.sh/ruff/
[ruff-format]: https://docs.astral.sh/ruff/formatter/
