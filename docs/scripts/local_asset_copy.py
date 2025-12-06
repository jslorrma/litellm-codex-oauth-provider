#!/usr/bin/env python3
r"""
LocalAssetCopy MkDocs plugin module.

Copies local linked files outside the docs directory into a build asset folder and rewrites links.

Examples
--------
>>> # Copies linked file and rewrites link
>>> plugin.on_page_markdown("[myfile](../data/file.txt)")
'[myfile](assets/data/file.txt)'

Notes
-----
- Only copies files outside docs/ and rewrites relative links.
- Uses pathlib for robust path handling.
- Asset folder is docs/assets (can be changed).
"""

from __future__ import annotations

import logging
import pathlib
import re
import shutil
from typing import TYPE_CHECKING

from mkdocs.config import config_options
from mkdocs.plugins import BasePlugin

if TYPE_CHECKING:
    from mkdocs.structure.files import Files
    from mkdocs.structure.pages import Page


class LocalAssetCopyPlugin(BasePlugin):
    """
    Plugin to copy local linked files outside docs/ into docs/assets and rewrite links.

    Attributes
    ----------
    asset_dir : Path
        Directory to copy assets into (default: docs/assets).
    logger : logging.Logger
        Logger for plugin messages.
    """

    config_scheme = (("asset_dir", config_options.Type(str, default="assets")),)

    def __init__(self) -> None:
        super().__init__()
        self.asset_dir: pathlib.Path | None = None
        self.logger = logging.getLogger("mkdocs.plugins.local_asset_copy")
        self.logger.setLevel(logging.INFO)

    def on_config(self, config: dict) -> dict:
        """Set up asset directory path."""
        docs_dir = pathlib.Path(config["docs_dir"])
        asset_dir = docs_dir / self.config.get("asset_dir", "assets")
        asset_dir.mkdir(parents=True, exist_ok=True)
        self.asset_dir = asset_dir
        return config

    def on_page_markdown(self, markdown: str, page: Page, config: dict, files: Files) -> str:  # noqa: ARG002
        """Parse markdown for local links, copy files outside docs/ into asset_dir, and rewrite links."""
        docs_dir = pathlib.Path(config["docs_dir"])
        asset_dir = self.asset_dir or docs_dir / "assets"
        page_dir = pathlib.Path(page.file.abs_src_path).parent
        root_dir = docs_dir.parent
        link_pattern = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")

        def rewrite_link(match: re.Match) -> str:
            text, url = match.group(1), match.group(2)
            self.logger.debug(f"[local_asset_copy] Checking link: [{text}]({url})")
            if url.startswith(("http", "/", "#")):
                self.logger.debug(f"[local_asset_copy] Skipping external or anchor link: {url}")
                return match.group(0)
            src_path = (page_dir / url).resolve()
            self.logger.debug(f"[local_asset_copy] Resolved source path: {src_path}")
            if src_path.suffix in (".md", ".markdown", ".mdx", ".html"):
                self.logger.debug(f"[local_asset_copy] Skipping non-markdown file: {src_path}")
                return match.group(0)
            if not src_path.exists():
                self.logger.warning(f"[local_asset_copy] Linked file not found: {src_path}")
                return match.group(0)
            # Only copy if outside docs_dir
            try:
                src_path.relative_to(docs_dir)
                self.logger.debug(
                    f"[local_asset_copy] File is inside docs_dir, not copying: {src_path}"
                )
                return match.group(0)
            except ValueError:
                rel_path = src_path.relative_to(root_dir)
                dest_path = asset_dir / rel_path
                dest_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src_path, dest_path)
                # Compute how many levels up to go from page_dir to docs_dir
                levels = len(page_dir.relative_to(docs_dir).parts)
                new_url = f"{'../' * levels}{dest_path.relative_to(docs_dir)}"
                self.logger.info(
                    f"[local_asset_copy] Copied {src_path} to {dest_path} and rewrote link to "
                    f"{new_url} in {page.file.src_path}"
                )
                return f"[{text}]({new_url})"

        return link_pattern.sub(rewrite_link, markdown)


# add entry point for MkDocs plugin


def on_page_markdown(markdown: str, page: Page, config: dict, files: Files, **kwargs) -> str:  # noqa: ARG001
    """Process page markdown to copy and rewrite local asset links."""
    plugin = LocalAssetCopyPlugin()
    plugin.on_config(config)
    return plugin.on_page_markdown(markdown, page, config, files)
