"""Command Palette (Ctrl+Shift+P) for quick access to all commands."""
from textual.app import ComposeResult
from textual.containers import Container, Vertical
from textual.widgets import Input, Static, ListView, ListItem, Label, Button
from textual.screen import ModalScreen
from textual.message import Message
from textual import events


class CommandPaletteScreen(ModalScreen):
    """Fuzzy command search palette."""

    COMMANDS = [
        ("⚙️ Configure Provider", "configure_provider", "Ctrl+K Ctrl+S"),
        ("📁 Add Project Folder", "add_project", "Left Sidebar"),
        ("🔒 Manage Trust Folders", "manage_trust", "Left Sidebar"),
        ("➕ New Work History", "new_history", "Ctrl+T"),
        ("📂 Toggle Left Sidebar", "toggle_left", "F1"),
        ("📂 Toggle Right Sidebar", "toggle_right", "F2"),
        ("🔄 Cycle AI Mode", "cycle_mode", "F3"),
        ("✏️ Toggle Accept Edits", "toggle_edits", "F4"),
        ("🔍 Quick Switch History", "quick_switch", "Ctrl+P"),
        ("🔎 Search All Histories", "search_history", "Ctrl+Shift+F"),
        ("💾 Create Checkpoint", "checkpoint_create", "CLI"),
        ("⏪ Restore Checkpoint", "checkpoint_restore", "CLI"),
        ("📋 View Sessions", "sessions_list", "CLI"),
        ("🔗 Create Deep Link", "deeplink_create", "CLI"),
        ("📊 View Analytics", "view_analytics", "—"),
        ("📤 Export Session", "export_session", "—"),
        ("🎨 Change Theme", "change_theme", "—"),
        ("❓ Help", "help", "—"),
    ]

    def __init__(self):
        super().__init__()
        self.filtered_commands = list(self.COMMANDS)

    def compose(self) -> ComposeResult:
        yield Container(
            Static("⚡ Command Palette", id="palette-title"),
            Input(placeholder="Type a command...", id="palette-input"),
            ListView(id="command-list"),
            id="palette-container"
        )

    def on_mount(self) -> None:
        self._update_list()
        self.query_one("#palette-input").focus()

    def on_input_changed(self, event: Input.Changed) -> None:
        query = event.value.lower().strip()
        if query:
            self.filtered_commands = [
                cmd for cmd in self.COMMANDS
                if query in cmd[0].lower() or query in cmd[1].lower()
            ]
        else:
            self.filtered_commands = list(self.COMMANDS)
        self._update_list()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if self.filtered_commands:
            self._execute_command(self.filtered_commands[0][1])

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        if event.item:
            cmd_name = event.item.id.replace("cmd-", "")
            for cmd in self.filtered_commands:
                if cmd[1] == cmd_name:
                    self._execute_command(cmd[1])
                    break

    def _update_list(self):
        list_view = self.query_one("#command-list")
        list_view.clear()
        for name, cmd_id, shortcut in self.filtered_commands:
            item = ListItem(
                Label(f"{name}  [dim]{shortcut}[/dim]"),
                id=f"cmd-{cmd_id}"
            )
            list_view.append(item)

    def _execute_command(self, command: str):
        self.post_message(self.CommandExecuted(command))
        self.dismiss(command)

    class CommandExecuted(Message):
        def __init__(self, command: str):
            self.command = command
            super().__init__()
