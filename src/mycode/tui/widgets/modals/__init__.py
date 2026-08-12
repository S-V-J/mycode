"""Modal widgets."""
from mycode.tui.widgets.modals.setup_wizard import SetupWizardScreen, ProviderSettingsScreen, PayloadEditorScreen
from mycode.tui.widgets.modals.trust_dialog import TrustDialogScreen
from mycode.tui.widgets.modals.plan_approval import PlanApprovalScreen
from mycode.tui.widgets.modals.diff_approval import DiffApprovalScreen

__all__ = [
    "SetupWizardScreen", "ProviderSettingsScreen", "PayloadEditorScreen",
    "TrustDialogScreen", "PlanApprovalScreen", "DiffApprovalScreen"
]