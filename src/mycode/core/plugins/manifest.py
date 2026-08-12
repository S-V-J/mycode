"""Plugin manifest validation and schema definitions."""

import json
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Set
from pathlib import Path
from enum import Enum
import semver


class PluginType(str, Enum):
    """Types of plugins."""
    TOOL = "tool"
    SKILL = "skill"
    THEME = "theme"
    MCP_SERVER = "mcp_server"
    LSP = "lsp"
    HOOK = "hook"
    MONITOR = "monitor"
    ARTIFACT = "artifact"
    CHANNEL = "channel"
    GENERIC = "generic"


class DependencyType(str, Enum):
    """Types of plugin dependencies."""
    PLUGIN = "plugin"
    PYTHON_PACKAGE = "python_package"
    SYSTEM = "system"
    MCP_SERVER = "mcp_server"


@dataclass
class PluginDependency:
    """Plugin dependency specification."""
    name: str
    version: str  # semver constraint, e.g., "^1.0.0", ">=1.0.0 <2.0.0"
    type: DependencyType = DependencyType.PLUGIN
    optional: bool = False
    description: str = ""

    def satisfies(self, version: str) -> bool:
        """Check if a version satisfies this dependency constraint."""
        try:
            return semver.version_in_range(version, self.version)
        except Exception:
            return False


@dataclass
class PluginEntryPoint:
    """Plugin entry point definition."""
    name: str
    module: str
    class_name: str
    type: PluginType = PluginType.GENERIC
    config_schema: Optional[Dict[str, Any]] = None


@dataclass
class PluginManifest:
    """Plugin manifest with all metadata."""
    name: str
    version: str
    description: str
    author: str
    license: str = "MIT"
    homepage: str = ""
    repository: str = ""
    keywords: List[str] = field(default_factory=list)

    # Plugin type and entry points
    plugin_type: PluginType = PluginType.GENERIC
    entry_points: List[PluginEntryPoint] = field(default_factory=list)

    # Dependencies
    dependencies: List[PluginDependency] = field(default_factory=list)

    # Requirements
    python_version: str = ">=3.10"
    mycode_version: str = ">=0.5.0"

    # Configuration
    config_schema: Optional[Dict[str, Any]] = None
    default_config: Dict[str, Any] = field(default_factory=dict)

    # Permissions/capabilities
    permissions: List[str] = field(default_factory=list)  # e.g., "file:read", "network:http", "shell:exec"

    # Compatibility
    platforms: List[str] = field(default_factory=lambda: ["linux", "darwin", "win32"])

    def validate(self) -> List[str]:
        """Validate manifest and return list of errors."""
        errors = []

        # Name validation
        if not self.name:
            errors.append("Name is required")
        elif not re.match(r'^[a-z0-9][a-z0-9._-]*$', self.name):
            errors.append("Name must be lowercase alphanumeric with dots, underscores, or hyphens")

        # Version validation
        if not self.version:
            errors.append("Version is required")
        elif not semver.is_valid(self.version):
            errors.append(f"Invalid semver version: {self.version}")

        # Description validation
        if not self.description:
            errors.append("Description is required")
        elif len(self.description) > 200:
            errors.append("Description must be 200 characters or less")

        # Author validation
        if not self.author:
            errors.append("Author is required")

        # Entry points validation
        entry_point_names = set()
        for ep in self.entry_points:
            if not ep.name:
                errors.append("Entry point name is required")
            elif ep.name in entry_point_names:
                errors.append(f"Duplicate entry point name: {ep.name}")
            else:
                entry_point_names.add(ep.name)

            if not ep.module:
                errors.append(f"Entry point '{ep.name}': module is required")
            if not ep.class_name:
                errors.append(f"Entry point '{ep.name}': class_name is required")

        # Dependency validation
        dep_names = set()
        for dep in self.dependencies:
            if not dep.name:
                errors.append("Dependency name is required")
            elif dep.name in dep_names:
                errors.append(f"Duplicate dependency: {dep.name}")
            else:
                dep_names.add(dep.name)

            # Validate version constraint format
            try:
                semver.validate_range(dep.version)
            except Exception:
                errors.append(f"Invalid version constraint for '{dep.name}': {dep.version}")

        # Permissions validation
        valid_permissions = {
            "file:read", "file:write", "file:execute",
            "network:http", "network:websocket", "network:tcp",
            "shell:exec", "shell:spawn",
            "process:spawn", "process:signal",
            "mcp:connect", "mcp:tool_call", "mcp:resource_read",
            "config:read", "config:write",
            "plugin:install", "plugin:manage",
            "skill:execute", "skill:manage",
        }
        for perm in self.permissions:
            if perm not in valid_permissions:
                errors.append(f"Unknown permission: {perm}")

        return errors

    def get_required_permissions(self) -> Set[str]:
        """Get all required permissions for this plugin."""
        return set(self.permissions)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "author": self.author,
            "license": self.license,
            "homepage": self.homepage,
            "repository": self.repository,
            "keywords": self.keywords,
            "plugin_type": self.plugin_type.value,
            "entry_points": [
                {
                    "name": ep.name,
                    "module": ep.module,
                    "class_name": ep.class_name,
                    "type": ep.type.value,
                    "config_schema": ep.config_schema
                }
                for ep in self.entry_points
            ],
            "dependencies": [
                {
                    "name": dep.name,
                    "version": dep.version,
                    "type": dep.type.value,
                    "optional": dep.optional,
                    "description": dep.description
                }
                for dep in self.dependencies
            ],
            "python_version": self.python_version,
            "mycode_version": self.mycode_version,
            "config_schema": self.config_schema,
            "default_config": self.default_config,
            "permissions": self.permissions,
            "platforms": self.platforms,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PluginManifest":
        """Create manifest from dictionary."""
        entry_points = [
            PluginEntryPoint(
                name=ep["name"],
                module=ep["module"],
                class_name=ep["class_name"],
                type=PluginType(ep.get("type", "generic")),
                config_schema=ep.get("config_schema")
            )
            for ep in data.get("entry_points", [])
        ]

        dependencies = [
            PluginDependency(
                name=dep["name"],
                version=dep["version"],
                type=DependencyType(dep.get("type", "plugin")),
                optional=dep.get("optional", False),
                description=dep.get("description", "")
            )
            for dep in data.get("dependencies", [])
        ]

        return cls(
            name=data["name"],
            version=data["version"],
            description=data["description"],
            author=data["author"],
            license=data.get("license", "MIT"),
            homepage=data.get("homepage", ""),
            repository=data.get("repository", ""),
            keywords=data.get("keywords", []),
            plugin_type=PluginType(data.get("plugin_type", "generic")),
            entry_points=entry_points,
            dependencies=dependencies,
            python_version=data.get("python_version", ">=3.10"),
            mycode_version=data.get("mycode_version", ">=0.5.0"),
            config_schema=data.get("config_schema"),
            default_config=data.get("default_config", {}),
            permissions=data.get("permissions", []),
            platforms=data.get("platforms", ["linux", "darwin", "win32"]),
        )

    @classmethod
    def from_file(cls, path: Path) -> "PluginManifest":
        """Load manifest from plugin.json file."""
        with open(path, 'r') as f:
            data = json.load(f)
        return cls.from_dict(data)

    def to_file(self, path: Path):
        """Save manifest to plugin.json file."""
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, 'w') as f:
            json.dump(self.to_dict(), f, indent=2)


@dataclass
class PluginLockEntry:
    """Lock file entry for a plugin."""
    name: str
    version: str
    source: str  # "github", "local", "npm", "marketplace"
    source_url: str
    checksum: str
    dependencies: Dict[str, str] = field(default_factory=dict)  # name -> resolved version


@dataclass
class PluginLockFile:
    """Plugin lock file."""
    version: int = 1
    plugins: List[PluginLockEntry] = field(default_factory=list)
    resolved_at: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "version": self.version,
            "plugins": [
                {
                    "name": p.name,
                    "version": p.version,
                    "source": p.source,
                    "source_url": p.source_url,
                    "checksum": p.checksum,
                    "dependencies": p.dependencies
                }
                for p in self.plugins
            ],
            "resolved_at": self.resolved_at
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PluginLockFile":
        return cls(
            version=data.get("version", 1),
            plugins=[
                PluginLockEntry(
                    name=p["name"],
                    version=p["version"],
                    source=p["source"],
                    source_url=p["source_url"],
                    checksum=p["checksum"],
                    dependencies=p.get("dependencies", {})
                )
                for p in data.get("plugins", [])
            ],
            resolved_at=data.get("resolved_at", "")
        )

    def to_file(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, 'w') as f:
            json.dump(self.to_dict(), f, indent=2)

    @classmethod
    def from_file(cls, path: Path) -> "PluginLockFile":
        with open(path, 'r') as f:
            data = json.load(f)
        return cls.from_dict(data)