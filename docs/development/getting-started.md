<!-- markdownlint-disable MD046 -->
<!-- markdownlint-disable-next-line MD041 -->
## Overview

This guide helps you get started with developing in this project after you have completed the [installation](installation.md). This project provides a highly automated development workflow using Pixi and Direnv that makes it easy to work locally, test your code, and sync with Databricks.

The project contains Python modules in the `src/bitc_data_sdk` directory and corresponding tests in the `tests` directory. All configuration is managed through the `pyproject.toml` file, which defines dependencies, development tools, features, environments, and automated tasks.

??? info "Project Structure"

    | File / Directory            | Purpose                                                                  |
    | --------------------------- | ------------------------------------------------------------------------ |
    | `.github`                   | CI/CD workflow definitions and a PR template                             |
    | `src/bitc_data_sdk` | Project import modules                                                   |
    | `docs`                      | Documentation directory (better write docs there instead of `README.md`) |
    | `tests`                     | Python module unit- & integration tests                                  |
    | `.envrc`                    | Environment configuration loaded by `direnv`                            |
    | `.pre-commit-config.yaml`   | `git` hook definitions consumed by `pre-commit`                          |
    | `LICENSE`                   | The license in its long form                                             |
    | `mkdocs.yml`                | Documentation config consumed by `mkdocs`                                |
    | `pyproject.toml`            | Project information, dependencies, features, environments, and tasks     |
    | `pixi.lock`                 | Locked dependencies for reproducible installations                       |
    | `README.md`                 | General project overview, displayed when visiting GitHub repository      |

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

## Best Practices for Adding Dependencies

When you need to add a new package to the project, choose the right type:

1. **Runtime dependencies** (should always be added from PyPI for consistent wheels and Databricks installs):

   ```bash
   pixi add --pypi <package-name>
   ```
   - This adds the package to `[project.dependencies]` and installs from PyPI by default.
   - If you want to add a Conda package, use:
     ```bash
     pixi add <package-name>
     ```
   - **Best practice:** Use PyPI for runtime dependencies unless you need a specific Conda build. This ensures consistent wheels and source installs, especially for Databricks and CI/CD.

2. **Feature/development dependencies** (for a specific feature/environment):

   ```bash
   pixi add -f <feature-name> <package-name>
   ```
   Examples:
   ```bash
   pixi add -f test pytest-benchmark
   pixi add -f docs sphinx-rtd-theme
   pixi add -f lint mypy
   ```

3. **PyPI-only packages**:

   ```bash
   pixi add -f <feature-name> <package-name> --pypi
   ```

4. **Source dependencies (monorepo/local path/git):**
   - Use `[tool.uv.sources]` in the dependent project to specify the source for a package (see Pixi and uv docs).
   - Example:
     ```toml
     [tool.uv.sources]
     my-local-package = { path = "../my-local-package", editable = true }
     my-git-package = { git = "https://github.com/username/my-git-package.git", editable = false }
     ```
   - Reference the name in `[project.dependencies]` or `[tool.pixi.pypi-dependencies]`.

After adding dependencies, they will be automatically installed in the relevant environments.

## Development Workflow

The combination of Pixi and Direnv provides an automated development workflow:

1. **Enter the project directory** - Direnv automatically activates the development environment
2. **Make your changes** - Edit code, add tests, update documentation
3. **Run tasks** - Use `pixi run <task>` to test, lint, format, or build
4. **Commit** - Pre-commit hooks automatically run quality checks
5. **Sync to Databricks** - Use tasks to sync your work to Databricks workspace

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
| pre-commit-install    | Install pre-commit hooks                            | pre-commit  |
| pre-commit-all        | Run all pre-commit hooks on all files               | pre-commit  |
| convert-dbx-to-jupyter| Convert Databricks notebooks to Jupyter format      | local       |
| databricks-sync       | Sync code to Databricks workspace                   | local       |
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

- **Test Explorer Integration** - VS Code's test explorer is automatically configured in `.vscode/settings.json`
- **Python Interpreter** - Automatically detects the Pixi-managed Python environment
- **Linting and Formatting** - Ruff is configured for real-time code quality feedback

**Tip:** Open the "Testing" tab in VS Code to see all available tests and run them with one click.

### Databricks Integration

This project supports hybrid development workflows where you develop locally and test on Databricks:

**Sync your code to Databricks:**

This task syncs your local code to your user workspace on Databricks, making it available for execution:

```bash
pixi run databricks-sync
```

**Convert Databricks notebooks to Jupyter format for local editing:**

This task converts Databricks notebooks to Jupyter format, allowing you to edit them locally as notebooks in VS Code or JupyterLab:

```bash
pixi run convert-dbx-to-jupyter
```

**Get requirements from source files:**

To keep your runtime dependencies in sync with your source code, you can get all packages used in your source files and automatically add them to your project:

```bash
pixi run requirements-from-src
```

These tasks make it easy to move between local development and Databricks execution.

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

<!--
**Deploy documentation to GitHub Pages:**

```bash
pixi run -e docs docs-deploy <version> [<alias>]
```

Where `<alias>` can be `latest`, `stable`, or any custom name.
-->

The documentation includes:

- Getting Started guide
- API reference (auto-generated)
- Changelog
- Contributing guidelines
- Test coverage reports
- License and dependency information

### Publishing and Release Workflow

**Create a new release:**

1. Bump the version:

   ```bash
   pixi run -e build bump-version patch  # or minor, major
   ```

   This updates `src/bitc_data_sdk/_version.py` following [semantic versioning](https://semver.org/) and automatically commits the changes.

2. Build the package:

   ```bash
   pixi run -e build build
   ```

<!--
The CI/CD pipeline will automatically build and deploy to Artifactory when you merge a PR with a new version tag in `src/bitc_data_sdk/_version.py`.
-->

!!! attention "Artifactory Access"

    To publish packages, you need Artifactory credentials configured in your repository secrets. Check the repository settings to verify access.

## Git Hooks

We use [`pre-commit`][pre-commit] to run git hooks helping you to develop high-quality code.
The hooks are configured in the `.pre-commit-config.yaml` file and executed before commit.

For instance, [`ruff`][ruff] & [`ruff-format`][ruff-format] fix the code base in-place to adhere to reasonable
coding standards.
`mypy`[mypy] & [`ruff`][ruff] lint the code for correctness.
These tools are configured via `pyproject.toml` and `.pre-commit-config.yaml` files.

!!! info "Installation"

    The pre-commit hooks are automatically installed when running `pixi run post-install` during the initial setup.

    If you need to install them manually, run:

    ```sh
    pixi run pre-commit install
    ```

??? example "Available pre-commit hooks"
    {% raw %}

    ```yaml
    {% include "../../.pre-commit-config.yaml" %}
    ```

    {% endraw %}

## CI/CD Pipelines

This project uses Azure DevOps (ADO) pipelines for continuous integration and deployment. The pipeline templates are located in:

- `azure-pipelines-ci.yaml` (Continuous Integration)
- `azure-pipelines-cd.yaml` (Continuous Deployment)

??? example "Continuous Integration Pipeline"
    {% raw %}

    ```yaml
    {% include "../../azure-pipelines-ci.yaml" %}
    ```

    {% endraw %}

??? example "Continuous Deployment Pipeline"
    {% raw %}

    ```yaml
    {% include "../../azure-pipelines-cd.yaml" %}
    ```

    {% endraw %}

### CI Pipeline Overview

The CI pipeline runs on every branch and includes the following jobs:

| Job         | Purpose                                                      |
|-------------|--------------------------------------------------------------|
| lint        | Lint and format codebase using Ruff and Pixi                 |
| test        | Run tests and upload coverage reports                        |
| build       | Build the Python package (wheel)                             |
| versioncheck| Check current and previous versions using Pixi/Hatch         |
| sonarqube   | Run SonarQube analysis using Ruff linting report             |

- **Linting:** Uses `pixi run -e lint lint` and `pixi run -e lint format` for code quality.
- **Ruff SonarQube report:** Generates a SonarQube-compatible report with `ruff check . --output-format=sonarqube` and publishes it as a pipeline artifact.
- **Testing:** Uses `pixi run -e test test-with-coverage` and publishes test and coverage results.
- **Build:** Uses `pixi run -e build build` to create wheel distributions.
- **Version check:** Uses `pixi run -e build hatch version` to retrieve the current version and compares it to the previous published version.
- **SonarQube:** Consumes the Ruff SonarQube report for static analysis and quality gates.

### CD Pipeline Overview

The CD pipeline runs on the `develop` branch and includes:

| Job     | Purpose                                                      |
|---------|--------------------------------------------------------------|
| publish | Publish the built wheel to Azure Artifacts using Pixi/Twine  |
| tag     | Create and push a new git tag for the release                |

- **Publish:** Authenticates with Azure Artifacts and uploads the wheel using Twine.
- **Tag:** Creates and pushes a new git tag for the release version.

### Versioning, Tagging, and Publishing

- Versioning is managed via `pixi run -e build hatch version` and follows semantic versioning.
- Tagging and publishing are automated in the CD pipeline after a successful build and version change.
- Only non-pre-release versions are published and tagged.

### SonarQube Integration

- The Ruff linting report is generated in the CI pipeline and consumed by SonarQube for static analysis.
- SonarQube uses the report for quality gates and code health metrics.

### How to Trigger and Interpret Pipeline Results

- Pipelines are triggered automatically on branch updates and PRs.
- Results are visible in Azure DevOps under the pipeline runs.
- Lint, test, coverage, SonarQube, and publish results are available as pipeline artifacts and summary reports.

For more details, see the pipeline YAML files and the [Pixi documentation](https://pixi.sh/docs/).

[pre-commit]: https://pre-commit.com/
[ruff]: https://docs.astral.sh/ruff/
[ruff-format]: https://docs.astral.sh/ruff/formatter/
