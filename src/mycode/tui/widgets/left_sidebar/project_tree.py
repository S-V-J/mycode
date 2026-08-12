"""Left sidebar: Multi-Project & Work History Manager."""
from textual.app import ComposeResult
from textual.containers import Vertical, Horizontal
from textual.widgets import Tree, Button, Static, Input, Label
from textual.widgets.tree import TreeNode
from textual.message import Message
from mycode.core.workspace import workspace_manager, Project, WorkHistory


class ProjectTree(Static):
    """Left sidebar tree showing projects and work histories."""

    class HistorySelected(Message):
        def __init__(self, history_id: str, project_id: str = None):
            self.history_id = history_id
            self.project_id = project_id
            super().__init__()

    class NewHistoryRequested(Message):
        def __init__(self, project_id: str = None):
            self.project_id = project_id
            super().__init__()

    class ProjectActionRequested(Message):
        def __init__(self, action: str, project_id: str = None):
            self.action = action  # "add", "manage_trust", "rename", "delete"
            self.project_id = project_id
            super().__init__()

    class HistoryActionRequested(Message):
        def __init__(self, action: str, history_id: str, project_id: str = None):
            self.action = action  # "rename", "delete"
            self.history_id = history_id
            self.project_id = project_id
            super().__init__()

    def compose(self) -> ComposeResult:
        yield Label("PROJECTS & WORKSPACES", id="sidebar-title")
        yield Tree("Workspaces", id="project-tree")
        yield Horizontal(
            Button("➕ New Project", id="btn-new-project", variant="primary"),
            Button("⚙️ Trust", id="btn-manage-trust", variant="default"),
            id="sidebar-actions"
        )

    def on_mount(self) -> None:
        tree = self.query_one("#project-tree", Tree)
        tree.root.expand()
        self.refresh_tree()

    def refresh_tree(self):
        """Refresh the tree from workspace state."""
        tree = self.query_one("#project-tree", Tree)
        tree.clear()
        tree.root.expand()

        # Add projects
        for project in workspace_manager.state.projects:
            project_node = tree.root.add(
                f"📂 {project.name} (trusted: {project.trusted_folder}) ✓",
                data={"type": "project", "project_id": project.id},
                expand=True
            )
            # Add work histories
            for history in project.work_histories:
                project_node.add_leaf(
                    f"💬 {history.name}",
                    data={"type": "work_history", "history_id": history.id, "project_id": project.id}
                )
            # Add "New Work History" option
            project_node.add_leaf(
                "➕ New Work History...",
                data={"type": "new_history", "project_id": project.id}
            )

        # Ad-hoc section
        if workspace_manager.state.ad_hoc_histories:
            ad_hoc_node = tree.root.add("📂 (No Project) — Ad-hoc work", expand=True)
            for history in workspace_manager.state.ad_hoc_histories:
                ad_hoc_node.add_leaf(
                    f"💬 {history.name}",
                    data={"type": "work_history", "history_id": history.id, "project_id": None}
                )
            ad_hoc_node.add_leaf(
                "➕ New Work History...",
                data={"type": "new_history", "project_id": None}
            )

    def on_tree_node_selected(self, event: Tree.NodeSelected) -> None:
        """Handle node selection."""
        node = event.node
        data = node.data

        if not data:
            return

        if data.get("type") == "work_history":
            self.post_message(self.HistorySelected(
                history_id=data["history_id"],
                project_id=data.get("project_id")
            ))
        elif data.get("type") == "new_history":
            self.post_message(self.NewHistoryRequested(
                project_id=data.get("project_id")
            ))

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-new-project":
            self.post_message(self.ProjectActionRequested("add"))
        elif event.button.id == "btn-manage-trust":
            self.post_message(self.ProjectActionRequested("manage_trust"))

    def on_tree_node_highlighted(self, event: Tree.NodeHighlighted) -> None:
        """Could add context menu on right-click here."""
        pass


class ProjectNameInput(Static):
    """Inline input for renaming project/history."""

    def __init__(self, current_name: str, on_confirm, on_cancel):
        super().__init__()
        self.current_name = current_name
        self.on_confirm = on_confirm
        self.on_cancel = on_cancel

    def compose(self) -> ComposeResult:
        yield Input(value=self.current_name, id="rename-input")

    def on_mount(self) -> None:
        self.query_one("#rename-input", Input).focus()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        new_name = event.value.strip()
        if new_name and new_name != self.current_name:
            self.on_confirm(new_name)
        else:
            self.on_cancel()