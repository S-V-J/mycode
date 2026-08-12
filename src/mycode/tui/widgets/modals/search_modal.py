"""Cross-History Search modal (Ctrl+Shift+F)."""
from textual.app import ComposeResult
from textual.containers import Container, Vertical
from textual.widgets import Input, Static, ListView, ListItem, Label
from textual.screen import ModalScreen
from textual.message import Message
from mycode.core.workspace import workspace_manager
from mycode.core.cache import get_sessions


class SearchModalScreen(ModalScreen):
    """Search across all work histories."""

    def compose(self) -> ComposeResult:
        yield Container(
            Static("🔎 Search All Histories", id="search-title"),
            Input(placeholder="Search across all conversations...", id="search-input"),
            Static("Results will appear below", id="search-results-info"),
            ListView(id="search-results"),
            id="search-container"
        )

    def on_mount(self) -> None:
        self.query_one("#search-input").focus()

    def on_input_changed(self, event: Input.Changed) -> None:
        query = event.value.lower().strip()
        list_view = self.query_one("#search-results")
        list_view.clear()

        if not query or len(query) < 2:
            return

        # Search across all projects' work histories
        results = []
        for project in workspace_manager.state.projects:
            for history in project.work_histories:
                matches = self._search_history(history, query)
                if matches:
                    results.append((history, project.name, matches))

        # Search ad-hoc histories
        for history in workspace_manager.state.ad_hoc_histories:
            matches = self._search_history(history, query)
            if matches:
                results.append((history, "(No Project)", matches))

        for history, project_name, matches in results:
            for match_text, role in matches[:3]:  # Top 3 matches per history
                snippet = match_text[:100] + "..." if len(match_text) > 100 else match_text
                item = ListItem(
                    Label(f"[{project_name}] {history.name}: {snippet}"),
                    id=f"result-{history.id}"
                )
                list_view.append(item)

        self.query_one("#search-results-info").update(
            f"Found {len(results)} histories matching '{query}'"
        )

    def _search_history(self, history, query: str):
        """Search messages in a work history."""
        if not history.session_id:
            return []

        from mycode.core.cache import get_messages
        messages = get_messages(history.session_id)
        matches = []
        for role, content, _, _ in messages:
            if query in content.lower():
                matches.append((content, role))
        return matches

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        if event.item:
            history_id = event.item.id.replace("result-", "")
            self.post_message(self.HistorySelected(history_id))
            self.dismiss(history_id)

    class HistorySelected(Message):
        def __init__(self, history_id: str):
            self.history_id = history_id
            super().__init__()
