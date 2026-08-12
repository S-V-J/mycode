"""Output Styles - Custom formatting for agent responses."""
from enum import Enum
from dataclasses import dataclass
from typing import Optional


class OutputStyle(str, Enum):
    """Output formatting styles."""
    DEFAULT = "default"
    JSON = "json"
    YAML = "yaml"
    TABLE = "table"
    MARKDOWN = "markdown"
    CODE = "code"
    MINIMAL = "minimal"


@dataclass
class StyleConfig:
    """Configuration for an output style."""
    style: OutputStyle
    description: str

    def format_prompt_addition(self) -> str:
        """Return system prompt addition for this style."""
        additions = {
            OutputStyle.JSON: "\n\nOUTPUT FORMAT: Respond ONLY with valid JSON. No markdown, no explanations.",
            OutputStyle.YAML: "\n\nOUTPUT FORMAT: Respond ONLY with valid YAML. No markdown, no explanations.",
            OutputStyle.TABLE: "\n\nOUTPUT FORMAT: Present data in ASCII table format. Use | separators.",
            OutputStyle.MARKDOWN: "\n\nOUTPUT FORMAT: Use rich Markdown with headers, lists, code blocks.",
            OutputStyle.CODE: "\n\nOUTPUT FORMAT: Output ONLY code. No explanations unless requested.",
            OutputStyle.MINIMAL: "\n\nOUTPUT FORMAT: Be concise. No headers, no fluff. Just the answer.",
            OutputStyle.DEFAULT: "",
        }
        return additions.get(self.style, "")

    def post_process(self, text: str) -> str:
        """Post-process the output text."""
        if self.style == OutputStyle.MINIMAL:
            lines = text.strip().split("\n")
            # Remove headers and excessive whitespace
            lines = [l for l in lines if not l.startswith("#")]
            return "\n".join(lines).strip()
        return text


STYLE_DESCRIPTIONS = {
    OutputStyle.DEFAULT: "Standard markdown response",
    OutputStyle.JSON: "JSON only (for parsing)",
    OutputStyle.YAML: "YAML only (for configs)",
    OutputStyle.TABLE: "ASCII table format",
    OutputStyle.MARKDOWN: "Rich markdown with headers",
    OutputStyle.CODE: "Code only, no explanations",
    OutputStyle.MINIMAL: "Minimal, no headers",
}
