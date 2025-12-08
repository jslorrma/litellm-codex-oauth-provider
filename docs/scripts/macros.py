#!/usr/bin/env python3
"""Macros for MkDocs documentation generation."""

from __future__ import annotations

import logging
import pathlib
from contextlib import redirect_stdout
from os import devnull
from typing import TYPE_CHECKING

from git_changelog.cli import build_and_render

if TYPE_CHECKING:
    from mkdocs_macros.plugin import MacrosPlugin


def define_env(env: MacrosPlugin) -> None:
    """Define macros for the mkdocs environment."""

    @env.macro
    def make_changelog() -> str:
        with redirect_stdout(open(devnull, mode="w", encoding="utf-8")):  # noqa: PTH123
            _, rendered = build_and_render(
                repository=".", template="keepachangelog", convention="conventional"
            )
        return rendered

    @env.macro
    def make_readme() -> str:
        """Return a version of the original project README.md with updated paths."""
        with pathlib.Path("README.md").open(encoding="utf-8") as file:
            lines = file.readlines()

        def _replace_url(line: str, pattern: str, replace_pattern: str) -> str:
            if pattern in line:
                line = line.replace(pattern, replace_pattern)
                if not pathlib.Path(line).suffix:
                    line = line[:-1] + ".md\n"
            return line

        lines = [_replace_url(line, pattern="docs/", replace_pattern="./") for line in lines]
        return "".join(lines)

    @env.macro
    def make_api_reference() -> str:
        """Return the API reference."""
        root = pathlib.Path(__file__).parent.parent.parent
        if not root.exists():
            logging.error("Root path does not exist: %s", root)
            return ""
        module_path = root / "src" / "litellm_codex_oauth_provider"
        rendered_lines = (
            f"::: {'.'.join(path.relative_to(module_path.parent).with_suffix('').parts)}"
            for path in sorted(module_path.rglob("*.py"))
            if "__init__.py" not in str(path) and "__main__.py" not in str(path)
        )
        return "\n".join(rendered_lines)
