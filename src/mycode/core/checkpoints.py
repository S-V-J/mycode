"""Checkpointing module for MyCode - Session snapshots, rewind, and deep links."""

import json
import uuid
import hashlib
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any
from rich.console import Console

console = Console()


@dataclass
class Checkpoint:
    """A session checkpoint/snapshot."""
    id: str
    session_id: str
    name: str
    created_at: datetime
    message_count: int
    tool_calls_count: int
    files_modified: List[str]
    working_directory: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    # Full state snapshot
    messages: List[Dict[str, Any]] = field(default_factory=list)
    tool_history: List[Dict[str, Any]] = field(default_factory=list)
    file_hashes: Dict[str, str] = field(default_factory=dict)


class CheckpointManager:
    """Manages session checkpoints for rewind and recovery."""

    def __init__(self, config_path: Optional[Path] = None):
        self.config_path = config_path or Path.home() / ".mycode" / "checkpoints.json"
        self.checkpoints: Dict[str, Checkpoint] = {}
        self._load_config()

    def _load_config(self):
        """Load checkpoints from file."""
        if self.config_path.exists():
            try:
                with open(self.config_path, 'r') as f:
                    data = json.load(f)
                    for cp_data in data.get('checkpoints', []):
                        cp = Checkpoint(
                            id=cp_data['id'],
                            session_id=cp_data['session_id'],
                            name=cp_data['name'],
                            created_at=datetime.fromisoformat(cp_data['created_at']),
                            message_count=cp_data['message_count'],
                            tool_calls_count=cp_data['tool_calls_count'],
                            files_modified=cp_data.get('files_modified', []),
                            working_directory=cp_data['working_directory'],
                            metadata=cp_data.get('metadata', {}),
                            messages=cp_data.get('messages', []),
                            tool_history=cp_data.get('tool_history', []),
                            file_hashes=cp_data.get('file_hashes', {})
                        )
                        self.checkpoints[cp.id] = cp
            except Exception as e:
                console.print(f"[yellow]Warning: Failed to load checkpoints: {e}[/yellow]")

    def save_config(self):
        """Save checkpoints to file."""
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            'checkpoints': [
                {
                    'id': cp.id,
                    'session_id': cp.session_id,
                    'name': cp.name,
                    'created_at': cp.created_at.isoformat(),
                    'message_count': cp.message_count,
                    'tool_calls_count': cp.tool_calls_count,
                    'files_modified': cp.files_modified,
                    'working_directory': cp.working_directory,
                    'metadata': cp.metadata,
                    'messages': cp.messages,
                    'tool_history': cp.tool_history,
                    'file_hashes': cp.file_hashes
                }
                for cp in self.checkpoints.values()
            ]
        }
        with open(self.config_path, 'w') as f:
            json.dump(data, f, indent=2)

    def create_checkpoint(self, session_id: str, name: str,
                          messages: List[Dict], tool_history: List[Dict],
                          file_hashes: Dict[str, str],
                          working_directory: str) -> str:
        """Create a new checkpoint."""
        checkpoint_id = str(uuid.uuid4())[:8]
        checkpoint = Checkpoint(
            id=checkpoint_id,
            session_id=session_id,
            name=name,
            created_at=datetime.now(),
            message_count=len(messages),
            tool_calls_count=len(tool_history),
            files_modified=list(file_hashes.keys()),
            working_directory=working_directory,
            messages=messages,
            tool_history=tool_history,
            file_hashes=file_hashes
        )
        self.checkpoints[checkpoint.id] = checkpoint
        self.save_config()
        return checkpoint.id

    def get_checkpoint(self, checkpoint_id: str) -> Optional[Checkpoint]:
        """Get a checkpoint by ID."""
        return self.checkpoints.get(checkpoint_id)

    def list_checkpoints(self, session_id: Optional[str] = None) -> List[Checkpoint]:
        """List all checkpoints, optionally filtered by session."""
        checkpoints = list(self.checkpoints.values())
        if session_id:
            checkpoints = [cp for cp in checkpoints if cp.session_id == session_id]
        return sorted(checkpoints, key=lambda cp: cp.created_at, reverse=True)

    def delete_checkpoint(self, checkpoint_id: str) -> bool:
        """Delete a checkpoint."""
        if checkpoint_id in self.checkpoints:
            del self.checkpoints[checkpoint_id]
            self.save_config()
            return True
        return False

    def restore_checkpoint(self, checkpoint_id: str) -> Optional[Dict]:
        """Restore a checkpoint - returns the state to restore."""
        checkpoint = self.checkpoints.get(checkpoint_id)
        if not checkpoint:
            return None
        return {
            "messages": checkpoint.messages,
            "tool_history": checkpoint.tool_history,
            "file_hashes": checkpoint.file_hashes,
            "working_directory": checkpoint.working_directory
        }


class DeepLinkManager:
    """Manages deep links for session sharing."""

    def __init__(self, config_path: Optional[Path] = None):
        self.config_path = config_path or Path.home() / ".mycode" / "deeplinks.json"
        self.links: Dict[str, Dict] = {}
        self._load_config()

    def _load_config(self):
        """Load deep links from file."""
        if self.config_path.exists():
            try:
                with open(self.config_path, 'r') as f:
                    self.links = json.load(f)
            except Exception:
                self.links = {}

    def save_config(self):
        """Save deep links to file."""
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.config_path, 'w') as f:
            json.dump(self.links, f, indent=2)

    def create_link(self, session_id: str, cwd: str, name: str = "") -> str:
        """Create a deep link for a session."""
        link_id = str(uuid.uuid4())[:12]
        link_data = {
            "session_id": session_id,
            "cwd": cwd,
            "name": name,
            "created_at": datetime.now().isoformat()
        }
        self.links[link_id] = link_data
        self.save_config()
        return f"mycode://session/{link_id}"

    def resolve_link(self, link_id: str) -> Optional[Dict]:
        """Resolve a deep link to session data."""
        return self.links.get(link_id)

    def list_links(self) -> List[Dict]:
        """List all deep links."""
        return [
            {"id": k, **v}
            for k, v in self.links.items()
        ]


# Global instances
_checkpoint_manager: Optional['CheckpointManager'] = None
_deep_link_manager: Optional['DeepLinkManager'] = None


def get_checkpoint_manager(config_path: Optional[Path] = None) -> 'CheckpointManager':
    """Get or create the global checkpoint manager."""
    global _checkpoint_manager
    if _checkpoint_manager is None:
        _checkpoint_manager = CheckpointManager(config_path)
    return _checkpoint_manager


def get_deep_link_manager(config_path: Optional[Path] = None) -> 'DeepLinkManager':
    """Get or create the global deep link manager."""
    global _deep_link_manager
    if _deep_link_manager is None:
        _deep_link_manager = DeepLinkManager(config_path)
    return _deep_link_manager


# CLI command functions
def checkpoint_create(session_id: str, name: str, messages: List[Dict],
                      tool_history: List[Dict], file_hashes: Dict[str, str],
                      cwd: str) -> str:
    """Create a checkpoint."""
    manager = get_checkpoint_manager()
    return manager.create_checkpoint(session_id, name, messages, tool_history, file_hashes, cwd)


def checkpoint_list(session_id: Optional[str] = None) -> List[Dict]:
    """List checkpoints."""
    manager = get_checkpoint_manager()
    checkpoints = manager.list_checkpoints(session_id)
    return [
        {
            "id": cp.id,
            "name": cp.name,
            "created_at": cp.created_at.isoformat(),
            "message_count": cp.message_count,
            "tool_calls_count": cp.tool_calls_count,
            "files_modified": len(cp.files_modified)
        }
        for cp in checkpoints
    ]


def checkpoint_restore(checkpoint_id: str) -> Optional[Dict]:
    """Restore a checkpoint."""
    manager = get_checkpoint_manager()
    return manager.restore_checkpoint(checkpoint_id)


def checkpoint_delete(checkpoint_id: str) -> bool:
    """Delete a checkpoint."""
    manager = get_checkpoint_manager()
    return manager.delete_checkpoint(checkpoint_id)


def deeplink_create(session_id: str, cwd: str, name: str = "") -> str:
    """Create a deep link."""
    manager = get_deep_link_manager()
    return manager.create_link(session_id, cwd, name)


def deeplink_resolve(link_id: str) -> Optional[Dict]:
    """Resolve a deep link."""
    manager = get_deep_link_manager()
    return manager.resolve_link(link_id)


def deeplink_list() -> List[Dict]:
    """List all deep links."""
    manager = get_deep_link_manager()
    return manager.list_links()