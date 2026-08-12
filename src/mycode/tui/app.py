"""Main TUI v2 Application - IDE-like workspace."""
import asyncio
import json
import os
from pathlib import Path
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.widgets import Header, Footer, Static
from textual.screen import ModalScreen
from textual import events

from mycode.core.workspace import (
    provider_manager, workspace_manager, trusted_folder_manager,
    ProviderProfile, DEFAULT_PROVIDERS
)
from mycode.core.config import ensure_config
from mycode.tui.widgets.left_sidebar.project_tree import ProjectTree
from mycode.tui.widgets.center.tabbed_workspace import CenterTabs
from mycode.tui.widgets.right_sidebar.folder_manager import FolderManager
from mycode.tui.widgets.modals.setup_wizard import SetupWizardScreen
from mycode.tui.widgets.modals.trust_dialog import TrustDialogScreen
from mycode.tui.widgets.shared.status_bar import StatusBar


class MyCodeApp(App):
    """MyCode v2.0 - IDE-like Terminal Workspace."""

    CSS_PATH = "app.tcss"
    TITLE = "MyCode v2.0"
    SUB_TITLE = "Agentic Workspace"

    # Keybindings
    BINDINGS = [
        Binding("f1", "toggle_left", "📁 Projects", priority=True),
        Binding("f2", "toggle_right", "📂 Files", priority=True),
        Binding("f3", "cycle_mode", "🔄 Mode", priority=True),
        Binding("f4", "toggle_edits", "✏️ Edits", priority=True),
        Binding("ctrl+t", "new_tab", "➕ New Tab", priority=True),
        Binding("ctrl+w", "close_tab", "✕ Close Tab", priority=True),
        Binding("ctrl+tab", "next_tab", "➡️ Next Tab", priority=True),
        Binding("ctrl+shift+tab", "previous_tab", "⬅️ Prev Tab", priority=True),
        Binding("ctrl+shift+p", "command_palette", "⚡ Palette", priority=True),
        Binding("ctrl+p", "quick_switch", "🔍 Switch", priority=True),
        Binding("ctrl+shift+f", "search_history", "🔎 Search", priority=True),
        Binding("ctrl+k,ctrl+s", "provider_settings", "⚙️ Provider", priority=True),
        Binding("ctrl+c", "quit_or_interrupt", "❌ Quit/Stop", priority=True),
    ]

    def __init__(self):
        super().__init__()
        self.agent = None
        self.current_mode = "AUTO"
        self.accept_edits = True
        self._setup_complete = False

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Horizontal(id="main-layout"):
            yield ProjectTree(id="left-sidebar")
            yield CenterTabs(id="center-tabs")
            yield FolderManager(id="right-sidebar")
        yield StatusBar(id="status-bar")
        yield Footer()

    def on_mount(self) -> None:
        """Initialize the application."""
        # Load workspace state
        self.load_workspace_state()

        # Check if first run (no providers configured)
        if not provider_manager.providers:
            self.push_screen(SetupWizardScreen(), self.on_setup_complete)
        else:
            self.init_agent()
            self.restore_tabs()
            self._setup_complete = True

    def load_workspace_state(self):
        """Load persisted workspace state."""
        # Workspace manager already loads on import
        # Update UI preferences
        prefs = workspace_manager.state.ui_preferences
        left_sidebar = self.query_one("#left-sidebar", ProjectTree)
        right_sidebar = self.query_one("#right-sidebar", FolderManager)

        if not prefs.left_sidebar_open:
            left_sidebar.display = False
        if not prefs.right_sidebar_open:
            right_sidebar.display = False

    def on_setup_complete(self, result: bool):
        """Called when setup wizard completes."""
        if result:
            self.init_agent()
            self.restore_tabs()
            self._setup_complete = True
            self.notify("MyCode ready! Welcome to your workspace.", title="✅ Initialized")

    def init_agent(self):
        """Initialize the shared agent."""
        api_key = ensure_config()
        if not api_key:
            return

        # Get active provider profile
        active_profile = provider_manager.get_active()
        if active_profile:
            from mycode.core.llm_client import NemotronClient
            from mycode.core.agent import Agent
            from mycode.core.modes import AgentMode, get_mode_from_string

            # Create client with provider settings
            client = NemotronClient(
                active_profile.api_key,
                base_url=active_profile.base_url
            )

            mode = get_mode_from_string(self.current_mode)

            self.agent = Agent(
                client,
                mode=mode,
                accept_edits=self.accept_edits,
                approval_callback=self._on_plan_approval_request,
                diff_approval_callback=self._on_diff_approval_request
            )

            # Start RAG indexing for active project
            self._start_rag_for_active_project()

    def _start_rag_for_active_project(self):
        """Start RAG indexing for the active project folder."""
        center_tabs = self.query_one("#center-tabs", CenterTabs)
        if center_tabs.active:
            # Get active tab's project
            tab_id = center_tabs.active
            for history_id, tid in center_tabs.workspace_to_tab.items():
                if tid == tab_id:
                    history = workspace_manager.get_work_history(history_id)
                    if history and history.project_id:
                        project = workspace_manager.get_project(history.project_id)
                        if project:
                            from mycode.core.rag import index_directory, start_watcher
                            index_directory(Path(project.trusted_folder))
                            start_watcher(Path(project.trusted_folder))
                            break

    def restore_tabs(self):
        """Restore tabs from persisted state."""
        center_tabs = self.query_one("#center-tabs", CenterTabs)
        center_tabs.restore_tabs()

        # Update right sidebar for active tab
        if center_tabs.active:
            self.update_right_sidebar_for_active_tab()

    def update_right_sidebar_for_active_tab(self):
        """Update right sidebar folder tree based on active tab's project."""
        center_tabs = self.query_one("#center-tabs", CenterTabs)
        folder_manager = self.query_one("#right-sidebar", FolderManager)

        if center_tabs.active:
            for history_id, tab_id in center_tabs.workspace_to_tab.items():
                if tab_id == center_tabs.active:
                    history = workspace_manager.get_work_history(history_id)
                    if history and history.project_id:
                        project = workspace_manager.get_project(history.project_id)
                        if project:
                            folder_manager.set_project_folder(project.trusted_folder)
                            break
                    else:
                        # Ad-hoc: use current directory
                        folder_manager.set_project_folder(".")
                    break

    # Event handlers for sidebar messages
    def on_project_tree_history_selected(self, event: ProjectTree.HistorySelected) -> None:
        """Open work history in center tabs."""
        center_tabs = self.query_one("#center-tabs", CenterTabs)

        # Check if already open
        if event.history_id in center_tabs.workspace_to_tab:
            tab_id = center_tabs.workspace_to_tab[event.history_id]
            center_tabs.active = tab_id
        else:
            # Add new tab
            history = workspace_manager.get_work_history(event.history_id)
            if history:
                tab_id = center_tabs.add_work_history(
                    event.history_id,
                    history.name,
                    event.project_id
                )
                center_tabs.active = tab_id

    def on_project_tree_new_history_requested(self, event: ProjectTree.NewHistoryRequested) -> None:
        """Create new work history and tab."""
        center_tabs = self.query_one("#center-tabs", CenterTabs)
        history = workspace_manager.add_work_history(event.project_id, "Untitled")
        tab_id = center_tabs.add_work_history(history.id, history.name, event.project_id)
        center_tabs.active = tab_id

        # Refresh left sidebar
        left_sidebar = self.query_one("#left-sidebar", ProjectTree)
        left_sidebar.refresh_tree()

    def on_project_tree_project_action_requested(self, event: ProjectTree.ProjectActionRequested) -> None:
        """Handle project actions."""
        if event.action == "add":
            self.action_add_project()
        elif event.action == "manage_trust":
            self.action_manage_trust()

    def on_center_tabs_tab_action_requested(self, event: CenterTabs.TabActionRequested) -> None:
        """Handle tab actions."""
        center_tabs = self.query_one("#center-tabs", CenterTabs)

        if event.action == "new":
            self.action_new_tab()
        elif event.action == "close":
            center_tabs.close_tab(event.tab_id)
        elif event.action == "switch":
            self.update_right_sidebar_for_active_tab()
            # Update agent CWD
            if event.history_id:
                history = workspace_manager.get_work_history(event.history_id)
                if history and history.project_id:
                    project = workspace_manager.get_project(history.project_id)
                    if project and self.agent:
                        self.agent.set_cwd(project.trusted_folder)

    def on_chat_workspace_message_submitted(self, event) -> None:
        """Handle message submission from chat workspace."""
        # Run agent with the message
        self.run_worker(self._run_agent(event.text, event.history_id, event.project_cwd), thread=True)

    async def _run_agent(self, user_input: str, history_id: str, project_cwd: str):
        """Run agent in background and stream updates."""
        if not self.agent:
            return

        try:
            # Set CWD for this request
            original_cwd = self.agent.cwd
            self.agent.set_cwd(project_cwd)

            # Capture output
            import io
            from contextlib import redirect_stdout, redirect_stderr
            stdout_capture = io.StringIO()
            stderr_capture = io.StringIO()

            with redirect_stdout(stdout_capture), redirect_stderr(stderr_capture):
                self.agent.run(user_input)

            output = stdout_capture.getvalue()
            if output:
                # Update the chat workspace
                center_tabs = self.query_one("#center-tabs", CenterTabs)
                for tab_id, pane in center_tabs._panes.items():
                    if hasattr(pane, 'history_id') and pane.history_id == history_id:
                        self.call_from_thread(pane.update_chat, output, True)
                        break

            # Save assistant response to session
            history = workspace_manager.get_work_history(history_id)
            if history and history.session_id:
                from mycode.core.cache import add_message
                add_message(history.session_id, "assistant", output)

        except Exception as e:
            self.call_from_thread(self.notify, f"Error: {e}", severity="error")
        finally:
            self.agent.set_cwd(original_cwd)

    # Actions
    def action_toggle_left(self) -> None:
        sidebar = self.query_one("#left-sidebar")
        sidebar.display = not sidebar.display
        workspace_manager.state.ui_preferences.left_sidebar_open = sidebar.display
        workspace_manager.save()

    def action_toggle_right(self) -> None:
        sidebar = self.query_one("#right-sidebar")
        sidebar.display = not sidebar.display
        workspace_manager.state.ui_preferences.right_sidebar_open = sidebar.display
        workspace_manager.save()

    def action_cycle_mode(self) -> None:
        modes = ["AUTO", "PLAN", "MANUAL", "AEROPLANE", "DONT_ASK", "BYPASS"]
        current_idx = modes.index(self.current_mode) if self.current_mode in modes else 0
        self.current_mode = modes[(current_idx + 1) % len(modes)]

        status_bar = self.query_one("#status-bar", StatusBar)
        status_bar.ai_mode = self.current_mode

        if self.agent:
            from mycode.core.modes import get_mode_from_string
            self.agent.set_mode(get_mode_from_string(self.current_mode))

        self.notify(f"Mode: {self.current_mode}", title="🔄 Mode Changed")

    def action_toggle_edits(self) -> None:
        self.accept_edits = not self.accept_edits
        status_bar = self.query_one("#status-bar", StatusBar)
        status_bar.accept_edits = "✓ ACCEPT" if self.accept_edits else "✗ REJECT"

        if self.agent:
            self.agent.set_accept_edits(self.accept_edits)

        self.notify(
            "Edits will execute silently." if self.accept_edits else "Edits require approval.",
            title="✏️ Edits"
        )

    def action_new_tab(self) -> None:
        """Create new tab - prompts for project."""
        center_tabs = self.query_one("#center-tabs", CenterTabs)
        # For now, create ad-hoc
        history = workspace_manager.add_work_history(None, "Untitled")
        tab_id = center_tabs.add_work_history(history.id, history.name, None)
        center_tabs.active = tab_id

        left_sidebar = self.query_one("#left-sidebar", ProjectTree)
        left_sidebar.refresh_tree()

    def action_close_tab(self) -> None:
        center_tabs = self.query_one("#center-tabs", CenterTabs)
        if center_tabs.active:
            center_tabs.close_tab(center_tabs.active)

    def action_next_tab(self) -> None:
        center_tabs = self.query_one("#center-tabs", CenterTabs)
        center_tabs.action("next_tab")

    def action_previous_tab(self) -> None:
        center_tabs = self.query_one("#center-tabs", CenterTabs)
        center_tabs.action("previous_tab")

    def action_add_project(self) -> None:
        """Add new project folder."""
        from textual.widgets import Input
        from textual.screen import ModalScreen
        from textual.containers import Container
        from textual.widgets import Button, Label

        class FolderPickerScreen(ModalScreen):
            def compose(self) -> ComposeResult:
                yield Container(
                    Label("Enter folder path:"),
                    Input(placeholder="/home/user/projects/myproject", id="folder-input"),
                    Horizontal(
                        Button("Cancel", id="cancel", variant="error"),
                        Button("Add", id="add", variant="success"),
                    ),
                    id="folder-picker"
                )

            def on_button_pressed(self, event: Button.Pressed) -> None:
                if event.button.id == "add":
                    path = self.query_one("#folder-input", Input).value
                    self.dismiss(path)
                else:
                    self.dismiss(None)

        async def handle_folder(path: str):
            if path and os.path.isdir(path):
                # Check if already trusted
                if not trusted_folder_manager.is_trusted(path):
                    # Show trust dialog
                    def on_trust(remember: bool):
                        if remember:
                            # Add to trusted folders
                            # Need to create project first
                            project_name = os.path.basename(path)
                            project = workspace_manager.add_project(project_name, path)
                            trusted_folder_manager.add_trusted(path, project.id)
                            # Refresh UI
                            left_sidebar = self.query_one("#left-sidebar", ProjectTree)
                            left_sidebar.refresh_tree()
                            # Auto-open first history
                            if project.work_histories:
                                center_tabs = self.query_one("#center-tabs", CenterTabs)
                                h = project.work_histories[0]
                                tab_id = center_tabs.add_work_history(h.id, h.name, project.id)
                                center_tabs.active = tab_id
                        else:
                            # Just allow for this session
                            pass

                    self.push_screen(
                        TrustDialogScreen(path, on_allow_callback=on_trust),
                        lambda _: None
                    )
                else:
                    # Already trusted, just add as project
                    project_name = os.path.basename(path)
                    project = workspace_manager.add_project(project_name, path)
                    left_sidebar = self.query_one("#left-sidebar", ProjectTree)
                    left_sidebar.refresh_tree()

        self.push_screen(FolderPickerScreen(), handle_folder)

    def action_manage_trust(self) -> None:
        """Manage trusted folders."""
        # Could show a modal with list of trusted folders
        self.notify("Trust management coming soon", title="⚙️ Trust")

    def action_command_palette(self) -> None:
        self.notify("Command Palette (Ctrl+Shift+P) - Coming soon", title="⚡ Palette")

    def action_quick_switch(self) -> None:
        self.notify("Quick Switch (Ctrl+P) - Coming soon", title="🔍 Switch")

    def action_search_history(self) -> None:
        self.notify("Search History (Ctrl+Shift+F) - Coming soon", title="🔎 Search")

    def action_provider_settings(self) -> None:
        """Open provider settings."""
        from mycode.tui.widgets.modals.setup_wizard import ProviderSettingsScreen
        self.push_screen(ProviderSettingsScreen(), lambda _: self.init_agent())

    def action_quit_or_interrupt(self) -> None:
        self.exit()

    # Plan/Diff approval callbacks (for agent)
    async def _on_plan_approval_request(self, plan) -> bool:
        from mycode.tui.widgets.modals.plan_approval import PlanApprovalScreen
        screen = PlanApprovalScreen(plan)
        result = await self.push_screen_wait(screen)
        return result

    async def _on_diff_approval_request(self, path: str, old_content: str, new_content: str) -> bool:
        from mycode.tui.widgets.modals.diff_approval import DiffApprovalScreen
        screen = DiffApprovalScreen(path, old_content, new_content)
        result = await self.push_screen_wait(screen)
        return result


if __name__ == "__main__":
    app = MyCodeApp()
    app.run()