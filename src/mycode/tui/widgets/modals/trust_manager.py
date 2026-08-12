"""Trust Folder Manager modal."""
from textual.app import ComposeResult
from textual.containers import Container, Vertical, Horizontal
from textual.widgets import Button, Static, ListView, ListItem, Label
from textual.screen import ModalScreen
from textual.message import Message

from mycode.core.workspace import trusted_folder_manager, workspace_manager


class TrustManagerScreen(ModalScreen):
    """Manage trusted folders."""

    def compose(self) -> ComposeResult:
        yield Container(
            Static("🔒 Trusted Folders Manager", id="trust-title"),
            Static("These folders have been granted access to MyCode:", id="trust-info"),
            ListView(id="trust-list"),
            Horizontal(
                Button("❌ Close", id="btn-close", variant="error"),
                id="trust-buttons"
            ),
            id="trust-container"
        )

    def on_mount(self) -> None:
        self._refresh_list()

    def _refresh_list(self):
        list_view = self.query_one("#trust-list")
        list_view.clear()

        for folder in trusted_folder_manager.folders:
            # Find associated project
            project_name = "—"
            for project in workspace_manager.state.projects:
                if project.id == folder.project_id:
                    project_name = project.name
                    break

            perms = ", ".join(folder.permissions)
            item = ListItem(
                Label(
                    f"📂 {folder.path}\n"
                    f"   Project: {project_name} | Permissions: {perms}\n"
                    f"   Acknowledged: {folder.acknowledged_at[:10]}"
                ),
                id=f"trust-{folder.path}"
            )
            list_view.append(item)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-close":
            self.dismiss(False)

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        if event.item:
            folder_path = event.item.id.replace("trust-", "")
            self.post_message(self.FolderSelected(folder_path))
            self.dismiss(folder_path)

    class FolderSelected(Message):
        def __init__(self, path: str):
            self.path = path
            super().__init__()
