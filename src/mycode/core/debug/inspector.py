"""Debug config inspector for MyCode."""
from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List
from pathlib import Path
import json


@dataclass
class ConfigSnapshot:
    """Snapshot of current configuration."""
    timestamp: str = field(default_factory=lambda: __import__('datetime').datetime.now().isoformat())
    config: Dict[str, Any] = field(default_factory=dict)
    providers: List[Dict[str, Any]] = field(default_factory=list)
    workspace: Dict[str, Any] = field(default_factory=dict)
    trusted_folders: List[str] = field(default_factory=list)
    environment: Dict[str, str] = field(default_factory=dict)
    active_profile: Optional[Dict[str, Any]] = None
    mode: str = "AUTO"
    accept_edits: bool = True

    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp,
            "config": self.config,
            "providers": self.providers,
            "workspace": {
                "projects": len(self.workspace.get("projects", [])),
                "ad_hoc_histories": len(self.workspace.get("ad_hoc_histories", [])),
                "open_tabs": len(self.workspace.get("tab_state", {}).get("tabs", [])),
            },
            "trusted_folders": self.trusted_folders,
            "environment": {k: "***" if "key" in k.lower() or "secret" in k.lower() or "token" in k.lower() else v
                          for k, v in self.environment.items()},
            "active_profile": self.active_profile,
            "mode": self.mode,
            "accept_edits": self.accept_edits,
        }

    def to_markdown(self) -> str:
        """Format as markdown for display."""
        lines = [
            f"# Debug Inspector — {self.timestamp}",
            "",
            "## Configuration",
            f"- Theme: {self.config.get('ui', {}).get('theme', 'N/A')}",
            f"- Font size: {self.config.get('ui', {}).get('font_size', 'N/A')}",
            f"- Animations: {self.config.get('ui', {}).get('animations', 'N/A')}",
            "",
            "## Active Provider",
        ]
        if self.active_profile:
            lines.extend([
                f"- Name: {self.active_profile.get('name', 'N/A')}",
                f"- Model: {self.active_profile.get('model', 'N/A')}",
                f"- Base URL: {self.active_profile.get('base_url', 'N/A')}",
                f"- API Key: {'***' + self.active_profile.get('api_key', '')[-4:] if self.active_profile.get('api_key') else 'N/A'}",
            ])
        else:
            lines.append("- No active profile")

        lines.extend([
            "",
            "## Workspace State",
            f"- Projects: {len(self.workspace.get('projects', []))}",
            f"- Ad-hoc histories: {len(self.workspace.get('ad_hoc_histories', []))}",
            f"- Open tabs: {len(self.workspace.get('tab_state', {}).get('tabs', []))}",
            "",
            "## Trusted Folders",
        ])
        for folder in self.trusted_folders:
            lines.append(f"- {folder}")

        lines.extend([
            "",
            "## Agent State",
            f"- Mode: {self.mode}",
            f"- Accept Edits: {self.accept_edits}",
            "",
            "## Environment (secrets redacted)",
        ])
        for k, v in self.environment.items():
            lines.append(f"- {k}: {v}")

        return "\n".join(lines)


class DebugInspector:
    """Inspect current configuration and context."""

    def __init__(self):
        self.snapshots: list = []

    def capture_snapshot(self) -> ConfigSnapshot:
        """Capture current configuration state."""
        from mycode.core.config import load_config
        from mycode.core.workspace import provider_manager, workspace_manager, trusted_folder_manager
        import os

        config = load_config()
        active = provider_manager.get_active()

        snapshot = ConfigSnapshot(
            config={
                "ui": {
                    "theme": config.ui.theme,
                    "font_size": config.ui.font_size,
                    "animations": config.ui.animations,
                }
            },
            providers=[p.to_dict() for p in provider_manager.providers],
            workspace=workspace_manager.state.to_dict(),
            trusted_folders=[f.path for f in trusted_folder_manager.folders],
            environment=dict(os.environ),
            active_profile=active.to_dict() if active else None,
        )

        self.snapshots.append(snapshot)
        return snapshot

    def get_latest_snapshot(self) -> Optional[ConfigSnapshot]:
        return self.snapshots[-1] if self.snapshots else None
