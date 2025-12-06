<!-- markdownlint-disable MD046 -->

# Developer Installation

## Requirements

### Pixi and Direnv

This project uses [`pixi`](https://pixi.sh/latest/) as a project and package manager. For automatic environment activation, we recommend [`direnv`](https://direnv.net/), but it is optional.

??? info "About Pixi and Direnv"

    - `pixi` is a cross-platform, multi-language package manager and workflow tool built on the foundation of the conda ecosystem. It provides developers with an experience similar to popular package managers like cargo or yarn, but for any language. Some of its key features include:

        - Support for conda and PyPi packages, with global dependency resolution.
        - Always includes an up-to-date lock file to ensure reproducibility.
        - Entirely written in Rust, making it super fast.
        - Supports workflow and task automation similar to `make`, `just` or `task`.

    - `direnv` is an environment switcher for the shell. It hooks into the shell to load or unload environment variables depending on the current directory, if a `.envrc` file is present. This allows for automatic activation and deactivation of virtual environments.

If you haven't installed `pixi` and (optionally) `direnv` yet, follow the installation instructions from the official documentation:

- [Pixi Installation](https://pixi.sh/latest/#installation)
- [Direnv](https://direnv.net/docs/installation.html)

For more information on doing Python development with `pixi`, please refer to this [tutorial](https://pixi.sh/latest/tutorials/python/).



!!! tip "WSL Recommendation"

    Instead of using Windows as a development environment, it is recommended to use the Windows Subsystem for Linux (WSL). Refer to the official Microsoft documentation for installing WSL and setting up your preferred Linux distribution.

## Installation Steps

This project utilizes `pixi` to provide a highly automated development environment. The combination of `pixi` and (optionally) `direnv` enables:

- **Automatic environment activation** when you enter the project directory (with `direnv`)
- **Consistent dependency management** across different machines and platforms
- **Automated setup** of development tools and pre-commit hooks

### Automated Setup (Recommended)

1. **Clone the repository:**

   ```bash
   git clone https://github.com/jslorrma/litellm-codex-oauth-provider.git
   cd litellm-codex-oauth-provider
   ```

2. **Allow direnv to load the environment (if using direnv):**

   When you first enter the directory, `direnv` will ask for permission:

   ```bash
   direnv allow
   ```

   This automatically installs all necessary dependencies and sets up the development environment.

3. **Verify the installation:**

   ```bash
   pixi list
   ```

   You should see all installed packages listed.

### Manual Installation (If Needed)

If you are not using `direnv` or the automated setup doesn't work, you can install and activate the environment manually:

```bash
# Install the local development environment
pixi install -e local-dev
pixi run post-install
```

To activate the shell manually:
```bash
pixi shell
```

Or install all environments at once:

```bash
pixi install --all
```

To install only specific environments:

```bash
# Install only testing dependencies
pixi install -e test

# Install only documentation dependencies
pixi install -e docs
```

??? failure "Common Installation Issues"

    In some cases, installation doesn't work right away. Here are solutions for common problems:

    | Problem                               | Solution                                         |
    | :------------------------------------ | :---------------------------------------------- |
    | _"I get a `ConnectionError`"_         | You may have proxy issues. Check your network settings. |
    | _"I destroyed my virtual environment"_ | Delete the `.pixi` folder and run `pixi install` again. |
    | _"Permission denied with direnv"_     | Run `direnv allow` in the project root directory. |
    | _"pixi command not found"_            | Install Pixi using the instructions above.      |
    | _"direnv command not found"_          | Install Direnv using the instructions above.    |

## Next Steps

Once installation is complete, see [Getting Started](getting-started.md) for details on project structure, development workflow, and available tasks.
