"""Center: Tabbed CLI Workspaces (VS Code-style)."""
from textual.app import ComposeResult
from textual.containers import Vertical, Horizontal
from textual.widgets import TabbedContent, TabPane, TextArea, Markdown, Static, Button, Label
from textual.message import Message
from textual import events
from mycode.core.workspace import workspace_manager, WorkHistory
from mycode.core.agent import Agent
from mycode.core.llm_client import NemotronClient
from mycode.core.config import ensure_config
from mycode.core.modes import get_mode_from_string
import io
from contextlib import redirect_stdout, redirect_stderr


class ChatWorkspace(Vertical):
    """Single tab content: chat messages + input area."""

    class MessageSubmitted(Message):
        def __init__(self, text: str, history_id: str, project_cwd: str):
            self.text = text
            self.history_id = history_id
            self.project_cwd = project_cwd
            super().__init__()

    def __init__(self, history_id: str, project_id: str = None, project_cwd: str = None):
        super().__init__()
        self.history_id = history_id
        self.project_id = project_id
        self.project_cwd = project_cwd or "."
        self.agent = None
        self.is_streaming = False
        self.current_response = ""

    def compose(self) -> ComposeResult:
        yield Markdown(
            "# New Conversation\n\n"
            "Type your request below. Press `Ctrl+Enter` to send.",
            id="chat-log"
        )
        yield Static("", id="tool-status")
        yield TextArea(
            "",
            id="chat-input",
            show_line_numbers=False,
            soft_wrap=True
        )

    def on_mount(self) -> None:
        self.init_agent()
        self.load_history()

    def init_agent(self):
        """Initialize agent for this workspace."""
        api_key = ensure_config()
        if api_key:
            client = NemotronClient(api_key)
            # Get mode from app
            from mycode.core.modes import AgentMode
            self.agent = Agent(
                client,
                mode=AgentMode.AUTO,
                accept_edits=True,
                approval_callback=None,
                diff_approval_callback=None
            )

    def load_history(self):
        """Load messages from SQLite session."""
        from mycode.core.cache import get_messages
        history = workspace_manager.get_work_history(self.history_id)
        if not history or not history.session_id:
            return

        messages = get_messages(history.session_id)
        if not messages:
            return

        chat_log = self.query_one("#chat-log", Markdown)
        md_content = ""
        for role, content, tool_calls, timestamp in messages:
            if role == "user":
                md_content += f"\n\n**You:** {content}"
            elif role == "assistant":
                md_content += f"\n\n**MyCode:** {content}"
        chat_log.update(md_content.strip())

    def on_text_area_submitted(self, event: TextArea.Submitted) -> None:
        """Handle user input (Ctrl+Enter)."""
        if self.is_streaming:
            return

        user_input = event.text_area.text.strip()
        if not user_input:
            return

        event.text_area.text = ""

        # Add user message to chat log
        chat_log = self.query_one("#chat-log", Markdown)
        chat_log.update(chat_log._markdown + f"\n\n**You:** {user_input}")

        # Save to session
        history = workspace_manager.get_work_history(self.history_id)
        if history and history.session_id:
            from mycode.core.cache import add_message
            add_message(history.session_id, "user", user_input)

        # Post message for app to handle agent run
        self.post_message(self.MessageSubmitted(user_input, self.history_id, self.project_cwd))


class CenterTabs(TabbedContent):
    """VS Code-style tabbed workspaces."""

    class TabActionRequested(Message):
        def __init__(self, action: str, tab_id: str = None, history_id: str = None):
            self.action = action  # "new", "close", "split", "duplicate", "rename"
            self.tab_id = tab_id
            self.history_id = history_id
            super().__init__()

    def __init__(self):
        super().__init__()
        self.workspace_to_tab: dict = {}  # history_id -> tab_id

    def compose(self) -> ComposeResult:
        # Tabs will be added dynamically
        yield Static("")  # Placeholder

    def on_mount(self) -> None:
        # Restore tabs from workspace state
        self.restore_tabs()

    def restore_tabs(self):
        """Restore tabs from persisted state."""
        tab_state = workspace_manager.state.tab_state
        for tab_info in tab_state.tabs:
            history_id = tab_info.get("work_history_id")
            title = tab_info.get("title", "Untitled")
            history = workspace_manager.get_work_history(history_id)
            if history:
                self.add_work_history(history_id, title, history.project_id)
                if tab_info.get("id") == tab_state.active_tab_id:
                    self.active = tab_info["id"]

    def add_work_history(self, history_id: str, title: str, project_id: str = None) -> str:
        """Add a new tab for a work history."""
        history = workspace_manager.get_work_history(history_id)
        if not history:
            return ""

        project_cwd = "."
        if project_id:
            project = workspace_manager.get_project(project_id)
            if project:
                project_cwd = project.trusted_folder

        tab_id = f"tab-{history_id}"
        pane = TabPane(
            ChatWorkspace(history_id, project_id, project_cwd),
            title=title,
            id=tab_id
        )
        self.add_pane(pane)
        self.workspace_to_tab[history_id] = tab_id

        # Update persisted tab state
        workspace_manager.state.tab_state.tabs.append({
            "id": tab_id,
            "work_history_id": history_id,
            "title": title,
            "dirty": False
        })
        workspace_manager.save()

        return tab_id

    def close_tab(self, tab_id: str):
        """Close a tab."""
        history_id = None
        for hid, tid in self.workspace_to_tab.items():
            if tid == tab_id:
                history_id = hid
                break

        if history_id:
            del self.workspace_to_tab[history_id]

        # Remove from persisted state
        workspace_manager.state.tab_state.tabs = [
            t for t in workspace_manager.state.tab_state.tabs if t["id"] != tab_id
        ]
        workspace_manager.save()

        self.remove_pane(tab_id)

    def on_tab_activated(self, event: TabbedContent.TabActivated) -> None:
        """Handle tab switch - update agent CWD and right sidebar."""
        tab_id = event.tab.id
        history_id = None
        for hid, tid in self.workspace_to_tab.items():
            if tid == tab_id:
                history_id = hid
                break

        if history_id:
            history = workspace_manager.get_work_history(history_id)
            if history:
                # Update active tab in persisted state
                workspace_manager.state.tab_state.active_tab_id = tab_id
                workspace_manager.save()

                # Notify app to update right sidebar and agent CWD
                self.post_message(self.TabActionRequested("switch", tab_id, history_id))

    def action_new_tab(self) -> None:
        """Create new work history and tab."""
        self.post_message(self.TabActionRequested("new"))

    def action_close_tab(self) -> None:
        """Close current tab."""
        if self.active:
            self.post_message(self.TabActionRequested("close", self.active))

    def action_next_tab(self) -> None:
        """Switch to next tab."""
        self.action("next_tab")

    def action_previous_tab(self) -> None:
        """Switch to previous tab."""
        self.action("previous_tab")