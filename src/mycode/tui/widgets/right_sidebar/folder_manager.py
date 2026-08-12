"""Right sidebar: System Folder Manager per work project."""
from textual.app import ComposeResult
from textual.containers import Vertical, Horizontal
from textual.widgets import Tree, Button, Static, Label
from textual.widgets.tree import TreeNode
from textual.message import Message
from mycode.core.workspace import workspace_manager
from pathlib import Path
import os


class FolderManager(Static):
    """Right sidebar showing folder tree for the active work project."""

    class FileActionRequested(Message):
        def __init__(self, action: str, file_path: str):
            self.action = action  # "open", "read", "edit", "delete", "copy_path", "add_context", "run_tests", "search"
            self.file_path = file_path
            super().__init__()

    def __init__(self):
        super().__init__()
        self.current_project_folder = "."

    def compose(self) -> ComposeResult:
        yield Label("SYSTEM FOLDER", id="folder-title")
        yield Horizontal(
            Button("🔒 Trust", id="btn-trust-settings", variant="default"),
            Button("🔄 Refresh", id="btn-refresh", variant="default"),
            id="folder-actions"
        )
        yield Tree("Folder", id="folder-tree")

    def on_mount(self) -> None:
        tree = self.query_one("#folder-tree", Tree)
        tree.root.expand()
        self.refresh_tree()

    def set_project_folder(self, folder_path: str):
        """Set the project folder to display."""
        self.current_project_folder = folder_path
        self.refresh_tree()

    def refresh_tree(self):
        """Refresh the folder tree."""
        tree = self.query_one("#folder-tree", Tree)
        tree.clear()
        tree.root.expand()

        path = Path(self.current_project_folder)
        if not path.exists():
            tree.root.add_leaf(f"Folder not found: {self.current_project_folder}")
            return

        self._build_tree(tree.root, path)

    def _build_tree(self, node: TreeNode, path: Path):
        """Recursively build tree with tree-sitter aware icons."""
        try:
            entries = sorted(path.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))
        except PermissionError:
            node.add_leaf("⛔ Permission denied")
            return

        for entry in entries:
            # Skip hidden and ignored directories
            if entry.name.startswith(".") and entry.name not in [".gitignore", ".env"]:
                continue
            if entry.name in ["__pycache__", "node_modules", "venv", ".venv", "dist", "build", ".git"]:
                continue

            if entry.is_dir():
                icon = "📁"
                child = node.add(f"{icon} {entry.name}", expand=False, data={"path": str(entry), "is_dir": True})
                # Add placeholder for lazy loading
                child.add_leaf("...", data={"placeholder": True})
            else:
                icon = self._get_file_icon(entry)
                node.add_leaf(f"{icon} {entry.name}", data={"path": str(entry), "is_dir": False})

    def _get_file_icon(self, path: Path) -> str:
        """Get icon based on file extension."""
        suffix = path.suffix.lower()
        if suffix == ".py":
            return "🐍"
        elif suffix in [".js", ".jsx", ".ts", ".tsx"]:
            return "📜"
        elif suffix in [".json", ".toml", ".yaml", ".yml"]:
            return "⚙️"
        elif suffix in [".md", ".txt", ".rst"]:
            return "📄"
        elif suffix in [".html", ".css", ".scss"]:
            return "🌐"
        elif suffix in [".sh", ".bash", ".zsh"]:
            return "💻"
        elif suffix in [".dockerfile", ".dockerignore"]:
            return "🐳"
        elif suffix in [".gitignore", ".gitattributes"]:
            return "🔧"
        else:
            return "📄"

    def on_tree_node_expanded(self, event: Tree.NodeExpanded) -> None:
        """Lazy load directory contents on expand."""
        node = event.node
        if node.children and node.children[0].data.get("placeholder"):
            # Remove placeholder and load real children
            node.remove_child(node.children[0])
            path = Path(node.data["path"])
            self._build_tree(node, path)

    def on_tree_node_selected(self, event: Tree.NodeSelected) -> None:
        """Handle file selection - could show preview or context menu."""
        node = event.node
        if node.data and not node.data.get("is_dir") and not node.data.get("placeholder"):
            # For now, just store the selected file
            self.selected_file = node.data["path"]

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-refresh":
            self.refresh_tree()
        elif event.button.id == "btn-trust-settings":
            # Could open trust manager
            pass

    def get_context_menu_actions(self, file_path: str) -> list:
        """Get available context menu actions for a file."""
        path = Path(file_path)
        actions = [
            ("Open in Editor", "open"),
            ("Read File", "read"),
            ("Edit File", "edit"),
            ("Delete", "delete"),
            ("Copy Path", "copy_path"),
            ("Add to Context", "add_context"),
        ]
        if path.suffix == ".py" and "test" in path.name.lower():
            actions.append(("Run Tests", "run_tests"))
        actions.append(("Search in Folder", "search"))
        return actions