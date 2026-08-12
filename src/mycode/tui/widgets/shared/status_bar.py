"""Shared widgets: Status bar."""
from textual.widgets import Static
from textual.reactive import reactive


class StatusBar(Static):
    """Bottom status bar showing AI Mode, Accept Edits, Project."""
    ai_mode = reactive("AUTO")
    accept_edits = reactive("✓ ACCEPT")
    project_name = reactive("No Project")

    def render(self) -> str:
        return f" {self.ai_mode}  |  {self.accept_edits}  |  📁 {self.project_name} "