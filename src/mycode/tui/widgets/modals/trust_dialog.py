"""Trust folder acknowledgment dialog."""
from textual.app import ComposeResult
from textual.containers import Container, Horizontal
from textual.widgets import Button, Checkbox, Label, Static
from textual.screen import ModalScreen


class TrustDialogScreen(ModalScreen):
    """Dialog for acknowledging trust for a folder."""

    def __init__(self, folder_path: str, on_allow_callback=None, on_deny_callback=None):
        super().__init__()
        self.folder_path = folder_path
        self.on_allow_callback = on_allow_callback
        self.on_deny_callback = on_deny_callback

    def compose(self) -> ComposeResult:
        yield Container(
            Static("🔒 Trust Folder Required", id="trust-title"),
            Static(f"MyCode needs access to: {self.folder_path}", id="trust-path"),
            Static("This allows:", id="trust-label"),
            Static("• Reading/writing files in this folder", classes="trust-item"),
            Static("• Running bash commands in this folder", classes="trust-item"),
            Static("• Indexing code for RAG context", classes="trust-item"),
            Checkbox("Remember this folder (add to trusted list)", id="remember-checkbox"),
            Horizontal(
                Button("Deny", id="btn-deny", variant="error"),
                Button("Allow & Trust", id="btn-allow", variant="success"),
                id="trust-buttons"
            ),
            id="trust-container"
        )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        remember = self.query_one("#remember-checkbox", Checkbox).value
        if event.button.id == "btn-allow":
            if self.on_allow_callback:
                self.on_allow_callback(remember)
            self.dismiss(True)
        elif event.button.id == "btn-deny":
            if self.on_deny_callback:
                self.on_deny_callback()
            self.dismiss(False)