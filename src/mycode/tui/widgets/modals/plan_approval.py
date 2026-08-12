"""Plan approval modal."""
from textual.app import ComposeResult
from textual.containers import Container, Horizontal
from textual.widgets import Button, Static
from textual.screen import ModalScreen
import json


class PlanApprovalScreen(ModalScreen):
    """Modal screen for approving execution plans in Plan Mode."""

    def __init__(self, plan):
        super().__init__()
        self.plan = plan
        self.approved = False

    def compose(self) -> ComposeResult:
        yield Container(
            Static("📋 Plan Approval Required", id="modal-title"),
            Static(f"Summary: {self.plan.summary}", id="modal-summary"),
            Static("Steps:", id="modal-steps-title"),
            *[
                Static(
                    f"  {i+1}. [bold]{step.name}[/bold] - {step.description}\n"
                    f"     Args: {json.dumps(step.args, indent=2)[:200]}"
                    f"{' [red]⚠ DESTRUCTIVE[/red]' if step.is_destructive else ''}",
                    classes="modal-step"
                )
                for i, step in enumerate(self.plan.steps)
            ],
            Horizontal(
                Button("✅ Approve & Execute", id="btn-approve", variant="success"),
                Button("❌ Reject", id="btn-reject", variant="error"),
                id="modal-buttons"
            ),
            id="modal-container"
        )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-approve":
            self.approved = True
            self.dismiss(True)
        elif event.button.id == "btn-reject":
            self.approved = False
            self.dismiss(False)