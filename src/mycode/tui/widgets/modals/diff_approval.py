"""Diff approval modal."""
from textual.app import ComposeResult
from textual.containers import Container, Horizontal
from textual.widgets import Button, Static
from textual.screen import ModalScreen
import difflib


class DiffApprovalScreen(ModalScreen):
    """Modal screen for approving file diffs."""

    def __init__(self, path: str, old_content: str, new_content: str):
        super().__init__()
        self.path = path
        self.old_content = old_content
        self.new_content = new_content
        self.approved = False

    def compose(self) -> ComposeResult:
        diff = list(difflib.unified_diff(
            self.old_content.splitlines(keepends=True),
            self.new_content.splitlines(keepends=True),
            fromfile=f"a/{self.path}",
            tofile=f"b/{self.path}",
            n=5
        ))
        diff_text = ''.join(diff) if diff else "No changes"

        yield Container(
            Static(f"✏️ Diff Approval: {self.path}", id="modal-title"),
            Static(diff_text, id="modal-diff"),
            Horizontal(
                Button("✅ Accept Changes", id="btn-accept", variant="success"),
                Button("❌ Reject Changes", id="btn-reject", variant="error"),
                id="modal-buttons"
            ),
            id="modal-container"
        )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-accept":
            self.approved = True
            self.dismiss(True)
        elif event.button.id == "btn-reject":
            self.approved = False
            self.dismiss(False)