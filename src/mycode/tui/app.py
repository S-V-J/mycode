import asyncio
import io
import json
import sys
from contextlib import redirect_stdout, redirect_stderr
from pathlib import Path
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, Container
from textual.widgets import (
    Header, Static, DirectoryTree, TextArea, Markdown,
    Tree, Button, Rule, LoadingIndicator, Input, Label, Checkbox
)
from textual.reactive import reactive
from textual.message import Message
from textual import events
from textual.screen import ModalScreen

from mycode.core.config import ensure_config
from mycode.core.llm_client import NemotronClient
from mycode.core.agent import Agent
from mycode.core.rag import index_directory, start_watcher
from mycode.core.cache import (
    get_or_create_default_session,
    get_sessions,
    create_session,
    add_message,
    get_messages,
    update_session_name,
    delete_session
)
from mycode.core.modes import AgentMode, ExecutionPlan, ToolCallPlan, get_mode_from_string, cycle_mode


class StatusBar(Static):
    """Bottom status bar showing AI Modes and Project context."""
    ai_mode = reactive("⏵⏵ AUTO")
    accept_edits = reactive("✓ ACCEPT EDITS")
    project_name = reactive("📁 mycode")

    def render(self):
        return f" {self.ai_mode}  |  {self.accept_edits}  |  {self.project_name} "


class PlanApprovalScreen(ModalScreen):
    """Modal screen for approving execution plans in Plan Mode."""

    def __init__(self, plan: ExecutionPlan):
        super().__init__()
        self.plan = plan
        self.approved = False

    def compose(self) -> ComposeResult:
        yield Container(
            Static("📋 Plan Approval Required", classes="modal-title"),
            Static(f"Summary: {self.plan.summary}", classes="modal-summary"),
            Static("Steps:", classes="modal-steps-title"),
            *[
                Static(
                    f"  {i+1}. [bold]{step.name}[/bold] - {step.description}\n"
                    f"     Args: {json.dumps(step.args, indent=2)[:200]}"
                    f"{' [red]⚠ DESTRUCTIVE[/red]' if step.is_destructive else ''}",
                    classes="modal-step"
                )
                for i, step in enumerate(self.plan.steps)
            ],
            Container(
                Button("✅ Approve & Execute", id="btn-approve", variant="success"),
                Button("❌ Reject", id="btn-reject", variant="error"),
                classes="modal-buttons"
            ),
            classes="modal-container"
        )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-approve":
            self.approved = True
            self.dismiss(True)
        elif event.button.id == "btn-reject":
            self.approved = False
            self.dismiss(False)


class DiffApprovalScreen(ModalScreen):
    """Modal screen for approving file diffs."""

    def __init__(self, path: str, old_content: str, new_content: str):
        super().__init__()
        self.path = path
        self.old_content = old_content
        self.new_content = new_content
        self.approved = False

    def compose(self) -> ComposeResult:
        import difflib
        diff = list(difflib.unified_diff(
            self.old_content.splitlines(keepends=True),
            self.new_content.splitlines(keepends=True),
            fromfile=f"a/{self.path}",
            tofile=f"b/{self.path}",
            n=5
        ))
        diff_text = ''.join(diff) if diff else "No changes"

        yield Container(
            Static(f"✏️ Diff Approval: {self.path}", classes="modal-title"),
            Static(diff_text, classes="modal-diff"),
            Container(
                Button("✅ Accept Changes", id="btn-accept", variant="success"),
                Button("❌ Reject Changes", id="btn-reject", variant="error"),
                classes="modal-buttons"
            ),
            classes="modal-container"
        )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-accept":
            self.approved = True
            self.dismiss(True)
        elif event.button.id == "btn-reject":
            self.approved = False
            self.dismiss(False)


class AgentMessage(Message):
    """Message sent from agent to TUI for streaming updates."""
    def __init__(self, content: str, is_final: bool = False, is_reasoning: bool = False):
        self.content = content
        self.is_final = is_final
        self.is_reasoning = is_reasoning
        super().__init__()


class SessionTree(Tree):
    """Custom tree widget for session management."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.project_path = str(Path.cwd())
        self.current_session_id = None

    def on_mount(self) -> None:
        self.refresh_sessions()

    def refresh_sessions(self):
        """Refresh the session tree from database."""
        self.clear()
        self.root.expand()
        project_name = Path(self.project_path).name
        proj = self.root.add(f"📁 {project_name}", expand=True)

        sessions = get_sessions(self.project_path)
        for session in sessions:
            session_id, name, _, _, _ = session
            proj.add_leaf(f"💬 {name}", data={"session_id": session_id})

        proj.add_leaf("➕ New Session...", data={"action": "new_session"})

    def on_tree_node_selected(self, event: Tree.NodeSelected) -> None:
        """Handle session selection."""
        node = event.node
        if node.data:
            if node.data.get("action") == "new_session":
                self.create_new_session()
            elif "session_id" in node.data:
                self.switch_session(node.data["session_id"])

    def create_new_session(self):
        """Create a new session."""
        session_id = create_session(f"Session {len(get_sessions(self.project_path)) + 1}", self.project_path)
        self.refresh_sessions()
        self.switch_session(session_id)

    def switch_session(self, session_id: str):
        """Switch to a different session."""
        self.current_session_id = session_id
        # Notify the app to load this session's messages
        self.post_message(SessionSelected(session_id))


class SessionSelected(Message):
    """Message sent when a session is selected."""
    def __init__(self, session_id: str):
        self.session_id = session_id
        super().__init__()


class LeftSidebar(Vertical):
    """Chat History & Project Management."""
    def compose(self) -> ComposeResult:
        yield Static("💬 PROJECTS & SESSIONS", classes="sidebar-title")
        yield SessionTree("MyCode Workspace", id="project-tree")
        yield Rule()
        yield Button("➕ New Project", id="btn-new-project", variant="primary")


class CenterChat(Vertical):
    """Main Interactive Chat Window."""
    def compose(self) -> ComposeResult:
        yield Markdown(
            "# Welcome to MyCode v2.0\n\n"
            "Type your request below.\n\n"
            "**Shortcuts:** `F1` (Chats) | `F2` (Files) | `F3` (Mode) | `F4` (Edits) | `Ctrl+P` (Palette)\n\n"
            "*Note: Press `Ctrl+Enter` in the input box to send your message.*",
            id="chat-log"
        )
        yield Rule()

        yield TextArea(
            "",
            id="chat-input",
            show_line_numbers=False,
            soft_wrap=True
        )


class RightSidebar(Vertical):
    """System Directory Management."""
    def compose(self) -> ComposeResult:
        yield Static("📂 SYSTEM DIRECTORY", classes="sidebar-title")
        yield DirectoryTree("./", id="file-tree")


class MyCodeApp(App):
    """The Main MyCode v2.0 Agentic TUI."""
    CSS_PATH = "app.tcss"
    TITLE = "MyCode v2.0"
    SUB_TITLE = "Agentic TUI"

    # SAFE BINDINGS: Function keys and Ctrl+P avoid terminal emulator conflicts
    BINDINGS = [
        Binding("f1", "toggle_left", "💬 Chats", priority=True),
        Binding("f2", "toggle_right", "📂 Files", priority=True),
        Binding("f3", "cycle_mode", "🔄 Mode", priority=True),
        Binding("f4", "toggle_edits", "✏️ Edits", priority=True),
        Binding("ctrl+p", "command_palette", "⚡ Palette", priority=True),
        Binding("ctrl+c", "quit_or_interrupt", "❌ Quit/Stop", priority=True),
    ]

    def __init__(self):
        super().__init__()
        self.agent = None
        self.current_response = ""
        self.is_streaming = False
        self.current_session_id = None
        self.pending_plan_approval = None
        self.pending_diff_approval = None

    def compose(self) -> ComposeResult:
        yield Header(show_clock=False)
        with Horizontal(id="main-layout"):
            yield LeftSidebar(id="left-sidebar")
            yield CenterChat(id="center-chat")
            yield RightSidebar(id="right-sidebar")
        yield StatusBar(id="status-bar")

    def on_mount(self) -> None:
        """Initialize the agent and start background indexing."""
        self.init_agent()

    def init_agent(self) -> None:
        """Initialize the agent with config and RAG."""
        api_key = ensure_config()
        client = NemotronClient(api_key)

        # Get current mode from status bar
        status_bar = self.query_one(StatusBar)
        mode = get_mode_from_string(status_bar.ai_mode)
        accept_edits = "ACCEPT" in status_bar.accept_edits

        self.agent = Agent(
            client,
            mode=mode,
            accept_edits=accept_edits,
            approval_callback=self._on_plan_approval_request,
            diff_approval_callback=self._on_diff_approval_request
        )

        # Start RAG indexing in background
        cwd = Path.cwd()
        index_directory(cwd)
        start_watcher(cwd)

        # Get or create default session
        self.current_session_id = get_or_create_default_session(str(cwd))
        self.load_session_messages(self.current_session_id)

        self.notify("MyCode ready! Type your request below.", title="✅ Initialized")

    async def _on_plan_approval_request(self, plan: ExecutionPlan) -> bool:
        """Handle plan approval request from agent."""
        self.pending_plan_approval = plan
        screen = PlanApprovalScreen(plan)
        result = await self.push_screen_wait(screen)
        self.pending_plan_approval = None
        return result

    async def _on_diff_approval_request(self, path: str, old_content: str, new_content: str) -> bool:
        """Handle diff approval request from agent."""
        self.pending_diff_approval = (path, old_content, new_content)
        screen = DiffApprovalScreen(path, old_content, new_content)
        result = await self.push_screen_wait(screen)
        self.pending_diff_approval = None
        return result

    def load_session_messages(self, session_id: str):
        """Load messages from a session into the chat log."""
        chat_log = self.query_one("#chat-log", Markdown)
        messages = get_messages(session_id)

        if not messages:
            # Welcome message for new session
            chat_log.update(
                "# Welcome to MyCode v2.0\n\n"
                "Type your request below.\n\n"
                "**Shortcuts:** `F1` (Chats) | `F2` (Files) | `F3` (Mode) | `F4` (Edits) | `Ctrl+P` (Palette)\n\n"
                "*Note: Press `Ctrl+Enter` in the input box to send your message.*"
            )
            return

        # Build markdown from messages
        md_content = ""
        for role, content, tool_calls, timestamp in messages:
            if role == "user":
                md_content += f"\n\n**You:** {content}"
            elif role == "assistant":
                md_content += f"\n\n**MyCode:** {content}"

        chat_log.update(md_content.strip())

    def on_session_selected(self, event: SessionSelected) -> None:
        """Handle session selection from the sidebar."""
        self.current_session_id = event.session_id
        self.load_session_messages(event.session_id)

    def on_text_area_submitted(self, event: TextArea.Submitted) -> None:
        """Handle user input submission (Ctrl+Enter)."""
        if self.is_streaming:
            return

        user_input = event.text_area.text.strip()
        if not user_input:
            return

        # Clear input
        event.text_area.text = ""

        # Add user message to chat log
        chat_log = self.query_one("#chat-log", Markdown)
        chat_log.update(chat_log._markdown + f"\n\n**You:** {user_input}")

        # Save user message to session
        add_message(self.current_session_id, "user", user_input)

        # Start agent streaming
        self.is_streaming = True
        self.current_response = ""
        self.run_worker(self.run_agent(user_input), thread=True)

    def run_agent(self, user_input: str) -> None:
        """Run the agent in a background thread and stream updates."""
        try:
            # Capture stdout/stderr
            stdout_capture = io.StringIO()
            stderr_capture = io.StringIO()

            with redirect_stdout(stdout_capture), redirect_stderr(stderr_capture):
                self.agent.run(user_input)

            # Get the output
            output = stdout_capture.getvalue()
            if output:
                self.call_from_thread(self.update_chat, output, True)

        except Exception as e:
            self.call_from_thread(self.update_chat, f"\n\n**Error:** {str(e)}", True)
        finally:
            self.call_from_thread(self.finish_streaming)

    def update_chat(self, content: str, is_final: bool = False) -> None:
        """Update the chat log with new content."""
        chat_log = self.query_one("#chat-log", Markdown)
        if is_final:
            self.current_response = content
            chat_log.update(chat_log._markdown + f"\n\n**MyCode:** {content}")
            # Save assistant response to session
            add_message(self.current_session_id, "assistant", content)
        else:
            # Streaming update - append to current response
            self.current_response += content
            chat_log.update(chat_log._markdown + content)

    def finish_streaming(self) -> None:
        """Called when agent finishes."""
        self.is_streaming = False

    def action_toggle_left(self) -> None:
        sidebar = self.query_one("#left-sidebar")
        sidebar.display = not sidebar.display

    def action_toggle_right(self) -> None:
        sidebar = self.query_one("#right-sidebar")
        sidebar.display = not sidebar.display

    def action_cycle_mode(self) -> None:
        status_bar = self.query_one(StatusBar)
        modes = ["⏵⏵ AUTO", "⏸ PLAN", "⏸ MANUAL", "✈️ AEROPLANE"]
        current = status_bar.ai_mode
        next_idx = (modes.index(current) + 1) % len(modes)
        new_mode_str = modes[next_idx]
        status_bar.ai_mode = new_mode_str
        self.sub_title = f"Mode: {new_mode_str}"

        # Update agent mode
        if self.agent:
            new_mode = get_mode_from_string(new_mode_str)
            self.agent.set_mode(new_mode)

        self.notify(f"Switched to {new_mode_str}", title="🔄 Mode Changed")

    def action_toggle_edits(self) -> None:
        status_bar = self.query_one(StatusBar)
        if "ACCEPT" in status_bar.accept_edits:
            status_bar.accept_edits = "✗ REJECT EDITS"
            self.notify("File edits will now require manual approval.", title="✏️ Edits")
        else:
            status_bar.accept_edits = "✓ ACCEPT EDITS"
            self.notify("File edits will execute silently.", title="✏️ Edits")

        # Update agent accept_edits setting
        if self.agent:
            accept_edits = "ACCEPT" in status_bar.accept_edits
            self.agent.set_accept_edits(accept_edits)

    def action_command_palette(self) -> None:
        self.notify("Command Palette coming soon! (/project, /clear, /help)", title="⚡ Palette")

    def action_quit_or_interrupt(self) -> None:
        if self.is_streaming:
            self.notify("Agent is running. Press again to force quit.", title="⚠️ Busy")
        else:
            self.exit()


if __name__ == "__main__":
    app = MyCodeApp()
    app.run()