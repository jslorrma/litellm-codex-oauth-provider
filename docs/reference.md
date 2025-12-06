# Reference

<!--
NOTE: To generate CLI reference documentation, you can use `mkdocs-typer`
      (https://github.com/bruce-szalwinski/mkdocs-typer) or `mkdocs-click`
      (https://github.com/mkdocs/mkdocs-click) plugins to automatically generate
      the CLI reference documentation from the command line interface (CLI) of your
      Python package (see examples below).
      Use `mkdocs-typer` plugin if your CLI is built with Typer, or use `mkdocs-click`
      plugin if your CLI is built with Click.
      Make sure to include the `mkdocs-typer` or `mkdocs-click` plugin in your
      `pyproject.toml` file under the `tool.pixi.feature.docs.pypi-dependencies`
      section, and you have it listed in the `markdown_extensions` section of your
      `mkdocs.yml` file.

TODO: Replace the CLI module path and command below with your project's actual CLI entry point.
      If your project does not provide a CLI, remove this section or add organization-specific API documentation here.
      Ensure any required secrets or configuration for CLI/API documentation are documented in your README and workflows.

## CLI

::: mkdocs-typer
  :module: bitc_data_sdk.cli.main
  :command: main
  :prog_name: bitc_data_sdk
  :depth: 2

::: mkdocs-click
    :module: bitc_data_sdk.cli.main
    :command: main
    :prog_name: bitc_data_sdk
    :depth: 2
-->

## API

{{ make_api_reference() }}
