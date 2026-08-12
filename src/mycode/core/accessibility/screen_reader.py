"""Screen reader support for MyCode TUI."""
from textual.widgets import Static
from typing import Optional


class ScreenReaderAnnouncer:
    """Announce events for screen readers."""

    def __init__(self, app=None):
        self.app = app
        self.enabled = False
        self._history: list = []

    def announce(self, message: str, priority: str = "polite"):
        """Announce a message to screen readers."""
        if not self.enabled:
            return
        self._history.append(message)
        # In Textual, use the accessibility API
        if self.app:
            self.app.announce(message, priority=priority)

    def announce_mode_change(self, mode: str):
        self.announce(f"AI mode changed to {mode}", priority="polite")

    def announce_tab_change(self, tab_name: str):
        self.announce(f"Switched to tab: {tab_name}", priority="polite")

    def announce_tool_execution(self, tool_name: str, status: str):
        self.announce(f"Tool {tool_name}: {status}", priority="assertive")

    def announce_error(self, error: str):
        self.announce(f"Error: {error}", priority="assertive")

    def toggle(self):
        self.enabled = not self.enabled
        return self.enabled


class AriaLabels:
    """ARIA label constants for TUI widgets."""

    LEFT_SIDEBAR = "Project and workspace navigation"
    RIGHT_SIDEBAR = "File browser"
    CHAT_INPUT = "Chat message input"
    COMMAND_PALETTE = "Command palette search"
    SETUP_WIZARD = "MyCode setup wizard"
    PLAN_APPROVAL = "Plan approval dialog"
    DIFF_APPROVAL = "File change approval dialog"
    MODE_BUTTON = "Cycle AI operational mode"
    EDITS_BUTTON = "Toggle accept edits mode"
