"""Artifact renderer for TUI visual outputs."""

import json
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Callable
from pathlib import Path
from enum import Enum
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.markdown import Markdown
from rich.syntax import Syntax
from rich.tree import Tree
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.layout import Layout
from rich.live import Live
import asyncio


class ArtifactType(str, Enum):
    """Types of artifacts."""
    HTML = "html"
    MARKDOWN = "markdown"
    CODE = "code"
    TABLE = "table"
    TREE = "tree"
    PANEL = "panel"
    PROGRESS = "progress"
    CHART = "chart"


@dataclass
class Artifact:
    """An artifact to be rendered in the TUI."""
    id: str
    type: ArtifactType
    title: str
    content: Any
    metadata: Dict[str, Any] = field(default_factory=dict)
    interactive: bool = False
    mime_type: str = "text/plain"


@dataclass
class ArtifactRenderer:
    """Renders artifacts in the TUI."""
    console: Console = field(default_factory=Console)

    def render(self, artifact: Artifact) -> None:
        """Render an artifact to the console."""
        if artifact.type == ArtifactType.HTML:
            self._render_html(artifact)
        elif artifact.type == ArtifactType.MARKDOWN:
            self._render_markdown(artifact)
        elif artifact.type == ArtifactType.CODE:
            self._render_code(artifact)
        elif artifact.type == ArtifactType.TABLE:
            self._render_table(artifact)
        elif artifact.type == ArtifactType.TREE:
            self._render_tree(artifact)
        elif artifact.type == ArtifactType.PANEL:
            self._render_panel(artifact)
        elif artifact.type == ArtifactType.PROGRESS:
            self._render_progress(artifact)
        else:
            self._render_default(artifact)

    def _render_html(self, artifact: Artifact):
        """Render HTML artifact (simplified - shows as markdown)."""
        # In a real implementation, this would use a proper HTML renderer
        # For now, render as markdown
        self.console.print(Panel(
            Markdown(str(artifact.content)),
            title=artifact.title,
            border_style="blue"
        ))

    def _render_markdown(self, artifact: Artifact):
        """Render markdown artifact."""
        self.console.print(Panel(
            Markdown(str(artifact.content)),
            title=artifact.title,
            border_style="green"
        ))

    def _render_code(self, artifact: Artifact):
        """Render code artifact with syntax highlighting."""
        language = artifact.metadata.get("language", "python")
        self.console.print(Panel(
            Syntax(str(artifact.content), language, theme="monokai", line_numbers=True),
            title=artifact.title,
            border_style="yellow"
        ))

    def _render_table(self, artifact: Artifact):
        """Render table artifact."""
        data = artifact.content
        if not isinstance(data, dict) or "columns" not in data or "rows" not in data:
            self.console.print("[red]Invalid table data format[/red]")
            return

        table = Table(title=artifact.title, show_header=True, header_style="bold magenta")
        for col in data["columns"]:
            table.add_column(col.get("name", ""), style=col.get("style", ""), justify=col.get("justify", "left"))

        for row in data["rows"]:
            table.add_row(*[str(cell) for cell in row])

        self.console.print(table)

    def _render_tree(self, artifact: Artifact):
        """Render tree artifact."""
        data = artifact.content
        if not isinstance(data, dict) or "root" not in data:
            self.console.print("[red]Invalid tree data format[/red]")
            return

        tree = Tree(data["root"].get("label", "Root"), style=data["root"].get("style", "bold"))

        def add_nodes(parent, nodes):
            for node in nodes:
                child = parent.add(node.get("label", ""), style=node.get("style", ""))
                if "children" in node:
                    add_nodes(child, node["children"])

        if "children" in data["root"]:
            add_nodes(tree, data["root"]["children"])

        self.console.print(Panel(tree, title=artifact.title, border_style="cyan"))

    def _render_panel(self, artifact: Artifact):
        """Render panel artifact."""
        self.console.print(Panel(
            str(artifact.content),
            title=artifact.title,
            border_style=artifact.metadata.get("border_style", "blue"),
            padding=artifact.metadata.get("padding", (1, 2))
        ))

    def _render_progress(self, artifact: Artifact):
        """Render progress artifact."""
        data = artifact.content
        if not isinstance(data, dict):
            return

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=self.console
        ) as progress:
            task = progress.add_task(data.get("description", "Processing..."), total=data.get("total", 100))
            # This is a snapshot - in reality would be updated live
            progress.update(task, completed=data.get("completed", 0))

    def _render_default(self, artifact: Artifact):
        """Default renderer."""
        self.console.print(Panel(
            str(artifact.content),
            title=artifact.title,
            border_style="white"
        ))


class ArtifactManager:
    """Manages artifact creation, storage, and rendering."""

    def __init__(self, config_dir: Path):
        self.config_dir = config_dir
        self.artifacts_dir = config_dir / "artifacts"
        self.artifacts_dir.mkdir(parents=True, exist_ok=True)
        self.renderer = ArtifactRenderer()
        self._artifact_cache: Dict[str, Artifact] = {}

    def create_artifact(
        self,
        artifact_type: ArtifactType,
        title: str,
        content: Any,
        metadata: Dict[str, Any] = None,
        interactive: bool = False
    ) -> Artifact:
        """Create a new artifact."""
        import uuid
        artifact_id = str(uuid.uuid4())[:8]

        artifact = Artifact(
            id=artifact_id,
            type=artifact_type,
            title=title,
            content=content,
            metadata=metadata or {},
            interactive=interactive
        )

        self._artifact_cache[artifact_id] = artifact
        return artifact

    def create_html(self, title: str, html_content: str, **kwargs) -> Artifact:
        """Create HTML artifact."""
        return self.create_artifact(ArtifactType.HTML, title, html_content, **kwargs)

    def create_markdown(self, title: str, markdown_content: str, **kwargs) -> Artifact:
        """Create markdown artifact."""
        return self.create_artifact(ArtifactType.MARKDOWN, title, markdown_content, **kwargs)

    def create_code(self, title: str, code: str, language: str = "python", **kwargs) -> Artifact:
        """Create code artifact."""
        metadata = kwargs.get("metadata", {})
        metadata["language"] = language
        kwargs["metadata"] = metadata
        return self.create_artifact(ArtifactType.CODE, title, code, **kwargs)

    def create_table(self, title: str, columns: List[Dict], rows: List[List], **kwargs) -> Artifact:
        """Create table artifact."""
        content = {"columns": columns, "rows": rows}
        return self.create_artifact(ArtifactType.TABLE, title, content, **kwargs)

    def create_tree(self, title: str, root_label: str, children: List[Dict], **kwargs) -> Artifact:
        """Create tree artifact."""
        content = {"root": {"label": root_label, "children": children}}
        return self.create_artifact(ArtifactType.TREE, title, content, **kwargs)

    def create_panel(self, title: str, content: str, border_style: str = "blue", **kwargs) -> Artifact:
        """Create panel artifact."""
        metadata = kwargs.get("metadata", {})
        metadata["border_style"] = border_style
        kwargs["metadata"] = metadata
        return self.create_artifact(ArtifactType.PANEL, title, content, **kwargs)

    def create_progress(self, title: str, description: str, completed: int = 0, total: int = 100, **kwargs) -> Artifact:
        """Create progress artifact."""
        content = {"description": description, "completed": completed, "total": total}
        return self.create_artifact(ArtifactType.PROGRESS, title, content, **kwargs)

    def render_artifact(self, artifact: Artifact):
        """Render an artifact."""
        self.renderer.render(artifact)

    def render_artifact_by_id(self, artifact_id: str):
        """Render an artifact by ID."""
        artifact = self._artifact_cache.get(artifact_id)
        if artifact:
            self.render_artifact(artifact)
        else:
            self.renderer.console.print(f"[red]Artifact '{artifact_id}' not found[/red]")

    def save_artifact(self, artifact: Artifact) -> Path:
        """Save artifact to disk."""
        file_path = self.artifacts_dir / f"{artifact.id}.json"
        data = {
            "id": artifact.id,
            "type": artifact.type.value,
            "title": artifact.title,
            "content": artifact.content,
            "metadata": artifact.metadata,
            "interactive": artifact.interactive,
            "mime_type": artifact.mime_type
        }
        with open(file_path, 'w') as f:
            json.dump(data, f, indent=2, default=str)
        return file_path

    def load_artifact(self, artifact_id: str) -> Optional[Artifact]:
        """Load artifact from disk."""
        file_path = self.artifacts_dir / f"{artifact_id}.json"
        if not file_path.exists():
            return None

        with open(file_path, 'r') as f:
            data = json.load(f)

        artifact = Artifact(
            id=data["id"],
            type=ArtifactType(data["type"]),
            title=data["title"],
            content=data["content"],
            metadata=data.get("metadata", {}),
            interactive=data.get("interactive", False),
            mime_type=data.get("mime_type", "text/plain")
        )
        self._artifact_cache[artifact_id] = artifact
        return artifact

    def list_artifacts(self) -> List[Artifact]:
        """List all saved artifacts."""
        artifacts = []
        for file_path in self.artifacts_dir.glob("*.json"):
            artifact = self.load_artifact(file_path.stem)
            if artifact:
                artifacts.append(artifact)
        return artifacts

    def delete_artifact(self, artifact_id: str) -> bool:
        """Delete an artifact."""
        file_path = self.artifacts_dir / f"{artifact_id}.json"
        if file_path.exists():
            file_path.unlink()
            if artifact_id in self._artifact_cache:
                del self._artifact_cache[artifact_id]
            return True
        return False


class InteractiveArtifact:
    """Base class for interactive artifacts."""

    def __init__(self, artifact_id: str, manager: ArtifactManager):
        self.artifact_id = artifact_id
        self.manager = manager
        self.state: Dict[str, Any] = {}

    async def handle_input(self, key: str) -> bool:
        """Handle keyboard input. Return True if handled."""
        return False

    async def update(self):
        """Update artifact state."""
        pass

    def render(self):
        """Render the artifact."""
        pass


class FormArtifact(InteractiveArtifact):
    """Interactive form artifact."""

    def __init__(self, artifact_id: str, manager: ArtifactManager, fields: List[Dict]):
        super().__init__(artifact_id, manager)
        self.fields = fields
        self.current_field = 0
        self.values = {}

    async def handle_input(self, key: str) -> bool:
        if key == "tab" or key == "enter":
            self.current_field = (self.current_field + 1) % len(self.fields)
            return True
        elif key == "shift+tab":
            self.current_field = (self.current_field - 1) % len(self.fields)
            return True
        elif key == "escape":
            return False  # Let parent handle

        # Handle field input
        field = self.fields[self.current_field]
        field_name = field["name"]

        if key == "backspace":
            self.values[field_name] = self.values.get(field_name, "")[:-1]
        elif len(key) == 1 and key.isprintable():
            self.values[field_name] = self.values.get(field_name, "") + key

        return True

    def render(self):
        from rich.console import Console
        from rich.panel import Panel
        from rich.text import Text

        console = Console()
        lines = []

        for i, field in enumerate(self.fields):
            prefix = "> " if i == self.current_field else "  "
            value = self.values.get(field["name"], "")
            placeholder = field.get("placeholder", "")
            display = value if value else f"[dim]{placeholder}[/dim]"

            lines.append(f"{prefix}[bold]{field['label']}:[/bold] {display}")

        console.print(Panel("\n".join(lines), title="Form", border_style="cyan"))


class SliderArtifact(InteractiveArtifact):
    """Interactive slider artifact."""

    def __init__(self, artifact_id: str, manager: ArtifactManager, min_val: float, max_val: float, step: float = 1, initial: float = 0):
        super().__init__(artifact_id, manager)
        self.min_val = min_val
        self.max_val = max_val
        self.step = step
        self.value = initial

    async def handle_input(self, key: str) -> bool:
        if key == "right" or key == "up":
            self.value = min(self.max_val, self.value + self.step)
            return True
        elif key == "left" or key == "down":
            self.value = max(self.min_val, self.value - self.step)
            return True
        elif key == "home":
            self.value = self.min_val
            return True
        elif key == "end":
            self.value = self.max_val
            return True
        return False

    def render(self):
        from rich.console import Console
        from rich.panel import Panel
        from rich.progress import Progress, BarColumn, TextColumn

        console = Console()
        progress = Progress(
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            console=console
        )
        task = progress.add_task("Value", total=self.max_val - self.min_val, completed=self.value - self.min_val)
        console.print(Panel(progress, title=f"Slider: {self.value}", border_style="green"))


class ToggleArtifact(InteractiveArtifact):
    """Interactive toggle artifact."""

    def __init__(self, artifact_id: str, manager: ArtifactManager, label: str, initial: bool = False):
        super().__init__(artifact_id, manager)
        self.label = label
        self.value = initial

    async def handle_input(self, key: str) -> bool:
        if key in ("enter", "space", "right", "left"):
            self.value = not self.value
            return True
        return False

    def render(self):
        from rich.console import Console
        from rich.panel import Panel

        console = Console()
        status = "[green]ON[/green]" if self.value else "[red]OFF[/red]"
        console.print(Panel(f"{self.label}: {status}", title="Toggle", border_style="blue"))


# MCP Connector for artifacts
class MCPArtifactConnector:
    """Connects artifacts to MCP servers for live data."""

    def __init__(self, mcp_client):
        self.mcp_client = mcp_client

    async def fetch_resource(self, uri: str) -> Any:
        """Fetch a resource from MCP server."""
        return await self.mcp_client.read_resource(uri)

    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Any:
        """Call an MCP tool."""
        return await self.mcp_client.call_tool(tool_name, arguments)

    async def get_prompt(self, prompt_name: str, arguments: Dict[str, Any]) -> Any:
        """Get an MCP prompt."""
        return await self.mcp_client.get_prompt(prompt_name, arguments)

    def create_live_artifact(
        self,
        title: str,
        resource_uri: str,
        refresh_interval: float = 5.0
    ) -> Artifact:
        """Create an artifact that auto-refreshes from an MCP resource."""
        # This would create a background task to refresh
        # For now, return a placeholder
        return Artifact(
            id="live_" + resource_uri.replace("/", "_").replace(":", ""),
            type=ArtifactType.MARKDOWN,
            title=title,
            content=f"Loading from {resource_uri}...",
            metadata={
                "live": True,
                "resource_uri": resource_uri,
                "refresh_interval": refresh_interval
            }
        )