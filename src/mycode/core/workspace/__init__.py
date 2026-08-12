"""Data models for TUI v2 workspace persistence."""
from dataclasses import dataclass, field, asdict
from typing import Optional, List, Dict, Any
from datetime import datetime
import uuid
import json
import os
from pathlib import Path


MYCODE_DIR = Path.home() / ".mycode"
MYCODE_DIR.mkdir(exist_ok=True, mode=0o700)

PROVIDERS_FILE = MYCODE_DIR / "providers.json"
WORKSPACES_FILE = MYCODE_DIR / "workspaces.json"
TRUSTED_FOLDERS_FILE = MYCODE_DIR / "trusted_folders.json"
CONFIG_FILE = MYCODE_DIR / "config.toml"


@dataclass
class ProviderProfile:
    """LLM provider configuration profile."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    api_key: str = ""
    base_url: str = ""
    model: str = ""
    raw_payload: Dict[str, Any] = field(default_factory=dict)
    is_default: bool = False
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    version: int = 1

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "ProviderProfile":
        return cls(**data)


@dataclass
class WorkHistory:
    """A chat session/work history linked to a project."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = "Untitled"
    session_id: str = ""  # SQLite session ID
    project_id: Optional[str] = None
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    is_active: bool = False
    version: int = 1


@dataclass
class Project:
    """A project with a trusted folder."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    trusted_folder: str = ""
    trusted_at: str = field(default_factory=lambda: datetime.now().isoformat())
    work_histories: List[WorkHistory] = field(default_factory=list)
    version: int = 1


@dataclass
class TabState:
    """Tab state for persistence."""
    active_tab_id: Optional[str] = None
    tabs: List[Dict[str, Any]] = field(default_factory=list)  # {id, work_history_id, title, dirty}


@dataclass
class UIPreferences:
    """UI preferences."""
    theme: str = "dark"
    left_sidebar_open: bool = True
    right_sidebar_open: bool = True
    font_size: int = 14
    version: int = 1


@dataclass
class WorkspaceState:
    """Complete workspace state for persistence."""
    projects: List[Project] = field(default_factory=list)
    ad_hoc_histories: List[WorkHistory] = field(default_factory=list)
    tab_state: TabState = field(default_factory=TabState)
    ui_preferences: UIPreferences = field(default_factory=UIPreferences)
    version: int = 1

    def to_dict(self) -> dict:
        return {
            "version": self.version,
            "projects": [self._project_to_dict(p) for p in self.projects],
            "ad_hoc_histories": [asdict(h) for h in self.ad_hoc_histories],
            "tab_state": asdict(self.tab_state),
            "ui_preferences": asdict(self.ui_preferences),
        }

    def _project_to_dict(self, project: Project) -> dict:
        return {
            **asdict(project),
            "work_histories": [asdict(h) for h in project.work_histories],
        }

    @classmethod
    def from_dict(cls, data: dict) -> "WorkspaceState":
        ws = cls()
        ws.version = data.get("version", 1)

        # Projects
        for p_data in data.get("projects", []):
            histories_data = p_data.pop("work_histories", [])
            project = Project(**p_data)
            project.work_histories = [WorkHistory(**h) for h in histories_data]
            ws.projects.append(project)

        # Ad-hoc histories
        ws.ad_hoc_histories = [WorkHistory(**h) for h in data.get("ad_hoc_histories", [])]

        # Tab state
        if "tab_state" in data:
            ws.tab_state = TabState(**data["tab_state"])

        # UI preferences
        if "ui_preferences" in data:
            ws.ui_preferences = UIPreferences(**data["ui_preferences"])

        return ws


@dataclass
class TrustedFolder:
    """A trusted folder with permissions."""
    path: str
    project_id: str
    acknowledged_at: str = field(default_factory=lambda: datetime.now().isoformat())
    permissions: List[str] = field(default_factory=lambda: ["read", "write", "execute", "index"])
    version: int = 1

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "TrustedFolder":
        return cls(**data)


# Default provider configurations
DEFAULT_PROVIDERS = [
    {
        "name": "NVIDIA Nemotron",
        "base_url": "https://integrate.api.nvidia.com/v1",
        "default_model": "nvidia/nemotron-3-ultra",
        "default_payload": {
            "model": "nvidia/nemotron-3-ultra",
            "temperature": 0.2,
            "max_tokens": 4096,
            "enable_thinking": True,
            "reasoning_budget": 2048,
            "top_p": 0.95,
            "frequency_penalty": 0.0,
            "presence_penalty": 0.0,
        }
    },
    {
        "name": "OpenAI",
        "base_url": "https://api.openai.com/v1",
        "default_model": "gpt-4o",
        "default_payload": {
            "model": "gpt-4o",
            "temperature": 0.2,
            "max_tokens": 4096,
            "top_p": 0.95,
            "frequency_penalty": 0.0,
            "presence_penalty": 0.0,
        }
    },
    {
        "name": "Ollama (Local)",
        "base_url": "http://localhost:11434/v1",
        "default_model": "llama3.1",
        "default_payload": {
            "model": "llama3.1",
            "temperature": 0.2,
            "max_tokens": 4096,
            "top_p": 0.95,
        }
    },
    {
        "name": "Together AI",
        "base_url": "https://api.together.xyz/v1",
        "default_model": "meta-llama/Meta-Llama-3.1-70B-Instruct-Turbo",
        "default_payload": {
            "model": "meta-llama/Meta-Llama-3.1-70B-Instruct-Turbo",
            "temperature": 0.2,
            "max_tokens": 4096,
            "top_p": 0.95,
        }
    },
    {
        "name": "OpenRouter",
        "base_url": "https://openrouter.ai/api/v1",
        "default_model": "anthropic/claude-3.5-sonnet",
        "default_payload": {
            "model": "anthropic/claude-3.5-sonnet",
            "temperature": 0.2,
            "max_tokens": 4096,
            "top_p": 0.95,
        }
    },
]


class ProviderManager:
    """Manages provider profiles."""

    def __init__(self):
        self.providers: List[ProviderProfile] = []
        self.active_profile_id: Optional[str] = None
        self._load()

    def _load(self):
        if PROVIDERS_FILE.exists():
            try:
                data = json.loads(PROVIDERS_FILE.read_text())
                self.providers = [ProviderProfile.from_dict(p) for p in data.get("profiles", [])]
                self.active_profile_id = data.get("active_profile_id")
            except Exception:
                self.providers = []
                self.active_profile_id = None
        else:
            self.providers = []
            self.active_profile_id = None

    def save(self):
        data = {
            "version": 1,
            "profiles": [p.to_dict() for p in self.providers],
            "active_profile_id": self.active_profile_id,
        }
        PROVIDERS_FILE.write_text(json.dumps(data, indent=2))

    def add_profile(self, profile: ProviderProfile) -> ProviderProfile:
        if profile.is_default:
            for p in self.providers:
                p.is_default = False
        self.providers.append(profile)
        if not self.active_profile_id:
            self.active_profile_id = profile.id
        self.save()
        return profile

    def get_active(self) -> Optional[ProviderProfile]:
        if self.active_profile_id:
            for p in self.providers:
                if p.id == self.active_profile_id:
                    return p
        return self.providers[0] if self.providers else None

    def set_active(self, profile_id: str):
        for p in self.providers:
            if p.id == profile_id:
                self.active_profile_id = profile_id
                self.save()
                return True
        return False

    def delete_profile(self, profile_id: str):
        self.providers = [p for p in self.providers if p.id != profile_id]
        if self.active_profile_id == profile_id:
            self.active_profile_id = self.providers[0].id if self.providers else None
        self.save()


class WorkspaceManager:
    """Manages workspace state (projects, histories, tabs)."""

    def __init__(self):
        self.state = WorkspaceState()
        self._load()

    def _load(self):
        if WORKSPACES_FILE.exists():
            try:
                data = json.loads(WORKSPACES_FILE.read_text())
                self.state = WorkspaceState.from_dict(data)
            except Exception:
                self.state = WorkspaceState()
        else:
            self.state = WorkspaceState()

    def save(self):
        WORKSPACES_FILE.write_text(json.dumps(self.state.to_dict(), indent=2))

    def add_project(self, name: str, trusted_folder: str) -> Project:
        project = Project(name=name, trusted_folder=trusted_folder)
        # Create initial work history
        history = WorkHistory(name="Untitled", project_id=project.id)
        project.work_histories.append(history)
        self.state.projects.append(project)
        self.save()
        return project

    def get_project(self, project_id: str) -> Optional[Project]:
        for p in self.state.projects:
            if p.id == project_id:
                return p
        return None

    def add_work_history(self, project_id: Optional[str], name: str = "Untitled") -> WorkHistory:
        history = WorkHistory(name=name, project_id=project_id)
        if project_id:
            project = self.get_project(project_id)
            if project:
                project.work_histories.append(history)
        else:
            self.state.ad_hoc_histories.append(history)
        self.save()
        return history

    def get_work_history(self, history_id: str) -> Optional[WorkHistory]:
        for p in self.state.projects:
            for h in p.work_histories:
                if h.id == history_id:
                    return h
        for h in self.state.ad_hoc_histories:
            if h.id == history_id:
                return h
        return None

    def rename_work_history(self, history_id: str, new_name: str):
        history = self.get_work_history(history_id)
        if history:
            history.name = new_name
            history.updated_at = datetime.now().isoformat()
            self.save()

    def delete_work_history(self, history_id: str):
        for p in self.state.projects:
            p.work_histories = [h for h in p.work_histories if h.id != history_id]
        self.state.ad_hoc_histories = [h for h in self.state.ad_hoc_histories if h.id != history_id]
        # Also remove from tab state
        self.state.tab_state.tabs = [t for t in self.state.tab_state.tabs if t.get("work_history_id") != history_id]
        self.save()


class TrustedFolderManager:
    """Manages trusted folders."""

    def __init__(self):
        self.folders: List[TrustedFolder] = []
        self._load()

    def _load(self):
        if TRUSTED_FOLDERS_FILE.exists():
            try:
                data = json.loads(TRUSTED_FOLDERS_FILE.read_text())
                self.folders = [TrustedFolder.from_dict(f) for f in data.get("folders", [])]
            except Exception:
                self.folders = []
        else:
            self.folders = []

    def save(self):
        TRUSTED_FOLDERS_FILE.write_text(json.dumps({"version": 1, "folders": [f.to_dict() for f in self.folders]}, indent=2))

    def is_trusted(self, path: str) -> bool:
        normalized = os.path.abspath(path)
        for f in self.folders:
            if os.path.abspath(f.path) == normalized:
                return True
        return False

    def add_trusted(self, path: str, project_id: str) -> TrustedFolder:
        folder = TrustedFolder(path=os.path.abspath(path), project_id=project_id)
        self.folders.append(folder)
        self.save()
        return folder

    def get_trusted(self, path: str) -> Optional[TrustedFolder]:
        normalized = os.path.abspath(path)
        for f in self.folders:
            if os.path.abspath(f.path) == normalized:
                return f
        return None

    def remove_trusted(self, path: str):
        normalized = os.path.abspath(path)
        self.folders = [f for f in self.folders if os.path.abspath(f.path) != normalized]
        self.save()


# Global instances
provider_manager = ProviderManager()
workspace_manager = WorkspaceManager()
trusted_folder_manager = TrustedFolderManager()