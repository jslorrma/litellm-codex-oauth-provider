#!/usr/bin/env python3
r"""
AutoAdmonition MkDocs plugin module.

Automatically converts >**Note**: style quotes and HTML details/summary elements into MkDocs admonitions.

Examples
--------
>>> # Converts HTML details to admonition
>>> plugin.convert_details("<details><summary>Warning</summary>Be careful!</details>")
'!!! warning "Warning"\n\n    Be careful!'

>>> # Converts quote block to admonition
>>> plugin.convert_notes("> **Note**: This is a note.")
'!!! note\n\n    This is a note.'

Notes
-----
- Uses inspect.cleandoc and textwrap.indent for robust content handling.
- Follows project coding standards and modern Python idioms.
"""

from __future__ import annotations

import inspect
import logging
import re
import textwrap

from mkdocs.config import config_options
from mkdocs.plugins import BasePlugin


class AutoAdmonitionPlugin(BasePlugin):
    """
    Plugin to automatically convert HTML details and note quotes to MkDocs admonitions.

    Attributes
    ----------
    smart_keywords : dict[str, list[str]]
        Maps admonition types to lists of keywords for smart detection.
    """

    config_scheme = (
        ("convert_details", config_options.Type(bool, default=True)),
        ("convert_notes", config_options.Type(bool, default=True)),
        ("details_collapsed", config_options.Type(bool, default=True)),
        ("notes_collapsed", config_options.Type(bool, default=False)),
        ("default_details_type", config_options.Type(str, default="info")),
        ("smart_type_detection", config_options.Type(bool, default=True)),
    )

    def __init__(self) -> None:
        super().__init__()
        self.smart_keywords: dict[str, list[str]] = {
            "warning": ["warning", "caution", "danger", "alert", "careful"],
            "tip": ["tip", "hint", "pro tip", "suggestion"],
            "note": ["note", "important", "remember", "notice"],
            "info": ["info", "information", "details"],
            "success": ["success", "done", "complete", "finished"],
            "example": ["example", "demo", "sample"],
            "question": ["question", "faq", "help"],
        }
        self.config = self._default_config()
        self.logger = logging.getLogger("mkdocs.plugins.auto_admonition")
        self.logger.setLevel(logging.DEBUG)

    def _default_config(self) -> dict:
        """Return a config dict with all default values."""
        return {
            "convert_details": True,
            "convert_notes": True,
            "details_collapsed": True,
            "notes_collapsed": False,
            "default_details_type": "info",
            "smart_type_detection": True,
        }

    def set_config(self, config: dict | None) -> None:
        """Merge user config with defaults."""
        if config:
            self.config.update({k: config.get(k, v) for k, v in self.config.items()})

    def on_page_markdown(self, markdown: str) -> str:
        """
        Process page markdown before it's converted to HTML.

        Parameters
        ----------
        markdown : str
            Markdown content of the page.

        Returns
        -------
        str
            Processed markdown content.
        """
        if self.config["convert_details"]:
            self.logger.info("[auto_admonition] Converting HTML <details> blocks to admonitions.")
            markdown = self._convert_block(
                markdown,
                pattern=r"<details>\s*<summary>(.*?)</summary>\s*(.*?)</details>",
                block_type="details",
            )
        if self.config["convert_notes"]:
            self.logger.info("[auto_admonition] Converting quoted note blocks to admonitions.")
            # Regex: match initial > **Note**: line and all consecutive quoted lines
            markdown = self._convert_block(
                markdown,
                pattern=r"(^>\s*\*\*(Note|Warning|Tip|Info|Important|Caution|Danger|Success|Example|Question)\*\*:.*(?:\n>[^\n]+)*)",
                block_type="note",
            )
        return markdown

    def _convert_block(self, content: str, pattern: str, block_type: str) -> str:
        """
        Generic block conversion for details and note quote sections.

        Streamlined to minimize duplication and use normalization for type detection.

        Parameters
        ----------
        content : str
            Input markdown or HTML content.
        pattern : str
            Regex pattern to match blocks.
        block_type : str
            Either 'details' or 'note'.

        Returns
        -------
        str
            Content with blocks converted to admonitions.
        """

        def replace(match: re.Match) -> str:
            if block_type == "details":
                summary, body = match.group(1).strip(), match.group(2).strip()
                title = summary
                raw_content = body
                collapsed = self.config["details_collapsed"]
                if self.config["smart_type_detection"]:
                    admon_type = self.detect_admonition_type(
                        summary, self.config["default_details_type"]
                    )
                else:
                    admon_type = self.config["default_details_type"]
                self.logger.debug(
                    f"[auto_admonition] Converted <details> block with summary '{summary}' to '{admon_type}' admonition."
                )
            else:
                note_type = match.group(2).lower() if match.group(2) else "note"
                block = match.group(0)
                # Extract only quoted lines
                quoted_lines = [
                    line[1:].strip() for line in block.splitlines() if line.startswith(">")
                ]
                if not note_type:
                    self.logger.warning(
                        "[auto_admonition] Note block type not recognized, defaulting to 'note'."
                    )
                else:
                    self.logger.debug(
                        f"[auto_admonition] Converted quoted block to '{note_type}' admonition."
                    )
                title = None
                # Remove the initial **Note**: from the first line
                if quoted_lines:
                    quoted_lines[0] = re.sub(r"^\*\*[^*]+\*\*: *", "", quoted_lines[0])
                raw_content = "\n".join(quoted_lines).strip()
                collapsed = self.config["notes_collapsed"]
                admon_type = note_type
            prefix = "???" if collapsed else "!!!"
            cleaned = inspect.cleandoc(raw_content)
            indented = textwrap.indent(cleaned, "    ")
            title_str = f' "{title}"' if title else ""
            return f"{prefix} {admon_type}{title_str}\n\n{indented}"

        flags = re.DOTALL | re.IGNORECASE if block_type == "details" else re.MULTILINE
        return re.sub(pattern, replace, content, flags=flags)

    def detect_admonition_type(self, summary: str, default_type: str) -> str:
        """
        Detect admonition type based on summary content.

        Parameters
        ----------
        summary : str
            The summary/title to analyze.
        default_type : str
            Fallback admonition type.

        Returns
        -------
        str
            Detected admonition type or default.
        """
        summary_lower = summary.lower()
        for admon_type, keywords in self.smart_keywords.items():
            if any(keyword in summary_lower for keyword in keywords):
                return admon_type
        return default_type


# add entry point for MkDocs plugin
def on_page_markdown(markdown: str, **kwargs: dict) -> str:
    """Process page markdown to convert both details and notes."""
    plugin = AutoAdmonitionPlugin()
    plugin.set_config(kwargs.get("config"))
    return plugin.on_page_markdown(markdown)
