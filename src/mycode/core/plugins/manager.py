"""Plugin manager for lifecycle management (install, uninstall, enable, disable)."""

import json
import shutil
import asyncio
import semver
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Set, Type
from pathlib import Path
from enum import Enum
from datetime import datetime
import importlib.util
import sys

from .manifest import (
    PluginManifest, PluginDependency, PluginType, DependencyType,
    PluginLockFile, PluginLockEntry
)
from .marketplace import MarketplaceManager, MarketplacePlugin


class PluginStatus(str, Enum):
    """Plugin installation status."""
    NOT_INSTALLED = "not_installed"
    INSTALLED = "installed"
    ENABLED = "enabled"
    DISABLED = "disabled"
    ERROR = "error"


@dataclass
class InstalledPlugin:
    """Information about an installed plugin."""
    manifest: PluginManifest
    path: Path
    status: PluginStatus = PluginStatus.INSTALLED
    installed_at: str = ""
    checksum: str = ""
    resolved_dependencies: Dict[str, str] = field(default_factory=dict)  # name -> version
    config: Dict[str, Any] = field(default_factory=dict)
    error: str = ""


class PluginManager:
    """Manages plugin lifecycle: install, uninstall, enable, disable."""

    def __init__(self, config_dir: Path, project_dir: Optional[Path] = None):
        self.config_dir = config_dir
        self.project_dir = project_dir or Path.cwd()
        self.user_plugins_dir = config_dir / "plugins"
        self.project_plugins_dir = self.project_dir / ".mycode" / "plugins"
        self.user_plugins_dir.mkdir(parents=True, exist_ok=True)
        self.project_plugins_dir.mkdir(parents=True, exist_ok=True)

        self.installed_plugins: Dict[str, InstalledPlugin] = {}
        self.marketplace_manager = MarketplaceManager(config_dir)
        self._load_installed_plugins()
        self._loaded_modules: Dict[str, Any] = {}

    def _load_installed_plugins(self):
        """Load installed plugins from both user and project directories."""
        # Load user plugins
        for plugin_dir in self.user_plugins_dir.iterdir():
            if plugin_dir.is_dir():
                self._load_plugin_from_dir(plugin_dir, "user")

        # Load project plugins (override user)
        for plugin_dir in self.project_plugins_dir.iterdir():
            if plugin_dir.is_dir():
                self._load_plugin_from_dir(plugin_dir, "project")

    def _load_plugin_from_dir(self, plugin_dir: Path, scope: str):
        """Load a plugin from its directory."""
        manifest_file = plugin_dir / "plugin.json"
        if not manifest_file.exists():
            return

        try:
            manifest = PluginManifest.from_file(manifest_file)

            # Check if already loaded (project overrides user)
            if manifest.name in self.installed_plugins:
                existing = self.installed_plugins[manifest.name]
                if existing.path.parent == self.project_plugins_dir and scope == "user":
                    return  # Skip user version if project version exists

            # Compute checksum
            checksum = self._compute_checksum(plugin_dir)

            # Load config
            config_file = plugin_dir / "config.json"
            config = {}
            if config_file.exists():
                with open(config_file, 'r') as f:
                    config = json.load(f)

            # Determine status
            status = PluginStatus.INSTALLED
            if config.get("enabled", True):
                status = PluginStatus.ENABLED
            else:
                status = PluginStatus.DISABLED

            installed = InstalledPlugin(
                manifest=manifest,
                path=plugin_dir,
                status=status,
                installed_at=datetime.fromtimestamp(plugin_dir.stat().st_mtime).isoformat(),
                checksum=checksum,
                config=config
            )
            self.installed_plugins[manifest.name] = installed
        except Exception as e:
            print(f"Warning: Failed to load plugin from {plugin_dir}: {e}")

    def _compute_checksum(self, path: Path) -> str:
        """Compute SHA256 checksum of plugin directory."""
        import hashlib
        hasher = hashlib.sha256()
        for file_path in sorted(path.rglob("*")):
            if file_path.is_file():
                hasher.update(file_path.read_bytes())
        return hasher.hexdigest()

    async def install(
        self,
        name: str,
        version: str = "latest",
        marketplace: str = None,
        scope: str = "user",  # "user" or "project"
        force: bool = False
    ) -> bool:
        """Install a plugin."""
        # Search for the plugin
        plugins = await self.marketplace_manager.search_plugins(query=name, marketplace=marketplace)

        # Filter by name
        candidates = [p for p in plugins if p.name == name]
        if not candidates:
            print(f"Plugin '{name}' not found in marketplaces")
            return False

        # Select version
        if version == "latest":
            candidate = max(candidates, key=lambda p: semver.VersionInfo.parse(p.version))
        else:
            matching = [p for p in candidates if p.version == version]
            if not matching:
                print(f"Version '{version}' not found for plugin '{name}'")
                return False
            candidate = matching[0]

        # Check if already installed
        if name in self.installed_plugins and not force:
            existing = self.installed_plugins[name]
            if existing.manifest.version == candidate.version:
                print(f"Plugin '{name}@{candidate.version}' already installed")
                return True

        # Resolve dependencies
        resolved_deps = await self._resolve_dependencies(candidate.manifest.dependencies)
        if not resolved_deps:
            print("Failed to resolve dependencies")
            return False

        # Determine install directory
        if scope == "project":
            install_dir = self.project_plugins_dir / name
        else:
            install_dir = self.user_plugins_dir / name

        # Remove existing if force
        if install_dir.exists():
            shutil.rmtree(install_dir)

        # Download plugin
        try:
            print(f"Downloading {name}@{candidate.version}...")
            await self.marketplace_manager.download_plugin(candidate, install_dir)
        except Exception as e:
            print(f"Download failed: {e}")
            if install_dir.exists():
                shutil.rmtree(install_dir)
            return False

        # Verify manifest
        manifest_file = install_dir / "plugin.json"
        if not manifest_file.exists():
            print("Invalid plugin: plugin.json not found")
            shutil.rmtree(install_dir)
            return False

        manifest = PluginManifest.from_file(manifest_file)
        errors = manifest.validate()
        if errors:
            print(f"Invalid plugin manifest: {errors}")
            shutil.rmtree(install_dir)
            return False

        # Install dependencies first
        for dep_name, dep_version in resolved_deps.items():
            if dep_name not in self.installed_plugins:
                print(f"Installing dependency: {dep_name}@{dep_version}")
                await self.install(dep_name, dep_version, scope=scope)

        # Create config file
        config = {
            "enabled": True,
            "installed_at": datetime.now().isoformat(),
            "scope": scope,
            "marketplace": candidate.marketplace,
            "checksum": self._compute_checksum(install_dir)
        }
        with open(install_dir / "config.json", 'w') as f:
            json.dump(config, f, indent=2)

        # Load the plugin
        self._load_plugin_from_dir(install_dir, scope)
        installed = self.installed_plugins[name]
        installed.resolved_dependencies = resolved_deps

        # Update lock file
        await self._update_lock_file()

        print(f"✓ Installed {name}@{manifest.version} ({scope})")
        return True

    async def _resolve_dependencies(
        self,
        dependencies: List[PluginDependency],
        resolved: Optional[Dict[str, str]] = None
    ) -> Optional[Dict[str, str]]:
        """Resolve plugin dependencies recursively."""
        if resolved is None:
            resolved = {}

        for dep in dependencies:
            if dep.optional:
                continue

            if dep.name in resolved:
                # Check if already resolved version satisfies constraint
                if not dep.satisfies(resolved[dep.name]):
                    print(f"Version conflict for {dep.name}: need {dep.version}, have {resolved[dep.name]}")
                    return None
                continue

            # Find best version
            versions = await self.marketplace_manager.get_plugin_versions(dep.name)
            matching = [v for v in versions if dep.satisfies(v)]
            if not matching:
                print(f"No matching version for dependency {dep.name} (constraint: {dep.version})")
                return None

            best_version = matching[0]  # Already sorted descending
            resolved[dep.name] = best_version

            # Recursively resolve this dependency's dependencies
            # We need to fetch the manifest for this version
            plugins = await self.marketplace_manager.search_plugins(query=dep.name)
            dep_plugin = next((p for p in plugins if p.name == dep.name and p.version == best_version), None)
            if dep_plugin and dep_plugin.manifest:
                sub_resolved = await self._resolve_dependencies(dep_plugin.manifest.dependencies, resolved)
                if sub_resolved is None:
                    return None
                resolved.update(sub_resolved)

        return resolved

    async def uninstall(self, name: str, scope: str = "user") -> bool:
        """Uninstall a plugin."""
        if name not in self.installed_plugins:
            print(f"Plugin '{name}' not installed")
            return False

        installed = self.installed_plugins[name]

        # Check if other plugins depend on this one
        dependents = self._get_dependents(name)
        if dependents:
            print(f"Cannot uninstall '{name}': required by {', '.join(dependents)}")
            return False

        # Remove plugin directory
        plugin_dir = installed.path
        if plugin_dir.exists():
            shutil.rmtree(plugin_dir)

        # Remove from loaded modules
        if name in self._loaded_modules:
            del self._loaded_modules[name]

        # Remove from installed plugins
        del self.installed_plugins[name]

        # Update lock file
        await self._update_lock_file()

        print(f"✓ Uninstalled {name}")
        return True

    def _get_dependents(self, name: str) -> List[str]:
        """Get plugins that depend on the given plugin."""
        dependents = []
        for plugin_name, installed in self.installed_plugins.items():
            if name in installed.resolved_dependencies:
                dependents.append(plugin_name)
        return dependents

    def enable(self, name: str) -> bool:
        """Enable a plugin."""
        if name not in self.installed_plugins:
            print(f"Plugin '{name}' not installed")
            return False

        installed = self.installed_plugins[name]
        if installed.status == PluginStatus.ENABLED:
            print(f"Plugin '{name}' already enabled")
            return True

        # Update config
        config_file = installed.path / "config.json"
        config = installed.config.copy()
        config["enabled"] = True
        with open(config_file, 'w') as f:
            json.dump(config, f, indent=2)

        installed.status = PluginStatus.ENABLED
        installed.config = config

        print(f"✓ Enabled {name}")
        return True

    def disable(self, name: str) -> bool:
        """Disable a plugin."""
        if name not in self.installed_plugins:
            print(f"Plugin '{name}' not installed")
            return False

        installed = self.installed_plugins[name]
        if installed.status == PluginStatus.DISABLED:
            print(f"Plugin '{name}' already disabled")
            return True

        # Update config
        config_file = installed.path / "config.json"
        config = installed.config.copy()
        config["enabled"] = False
        with open(config_file, 'w') as f:
            json.dump(config, f, indent=2)

        installed.status = PluginStatus.DISABLED
        installed.config = config

        # Unload module if loaded
        if name in self._loaded_modules:
            del self._loaded_modules[name]

        print(f"✓ Disabled {name}")
        return True

    def list_plugins(self, scope: str = None) -> List[InstalledPlugin]:
        """List installed plugins."""
        plugins = list(self.installed_plugins.values())

        if scope:
            plugins = [p for p in plugins if p.config.get("scope") == scope]

        return sorted(plugins, key=lambda p: p.manifest.name)

    def get_plugin(self, name: str) -> Optional[InstalledPlugin]:
        """Get installed plugin by name."""
        return self.installed_plugins.get(name)

    async def update(self, name: str) -> bool:
        """Update a plugin to latest version."""
        if name not in self.installed_plugins:
            print(f"Plugin '{name}' not installed")
            return False

        installed = self.installed_plugins[name]
        scope = installed.config.get("scope", "user")
        marketplace = installed.config.get("marketplace")

        return await self.install(name, version="latest", marketplace=marketplace, scope=scope, force=True)

    def load_plugin(self, name: str) -> Any:
        """Load a plugin's entry points."""
        if name not in self.installed_plugins:
            raise ValueError(f"Plugin '{name}' not installed")

        installed = self.installed_plugins[name]
        if installed.status != PluginStatus.ENABLED:
            raise ValueError(f"Plugin '{name}' is not enabled")

        if name in self._loaded_modules:
            return self._loaded_modules[name]

        # Add plugin directory to sys.path
        plugin_path = str(installed.path)
        if plugin_path not in sys.path:
            sys.path.insert(0, plugin_path)

        loaded = {}
        for entry_point in installed.manifest.entry_points:
            try:
                module = importlib.import_module(entry_point.module)
                cls = getattr(module, entry_point.class_name)
                loaded[entry_point.name] = cls
            except Exception as e:
                print(f"Warning: Failed to load entry point '{entry_point.name}': {e}")

        self._loaded_modules[name] = loaded
        return loaded

    def get_entry_point(self, plugin_name: str, entry_point_name: str) -> Any:
        """Get a specific entry point from a plugin."""
        loaded = self.load_plugin(plugin_name)
        return loaded.get(entry_point_name)

    async def _update_lock_file(self):
        """Update the plugin lock file."""
        lock_file = self.config_dir / "plugins.lock"
        entries = []

        for name, installed in self.installed_plugins.items():
            entry = PluginLockEntry(
                name=name,
                version=installed.manifest.version,
                source=installed.config.get("marketplace", "unknown"),
                source_url=installed.manifest.repository or "",
                checksum=installed.checksum,
                dependencies=installed.resolved_dependencies
            )
            entries.append(entry)

        lock = PluginLockFile(
            plugins=entries,
            resolved_at=datetime.now().isoformat()
        )
        lock.to_file(lock_file)

    def validate_permissions(self, name: str, required_permissions: Set[str]) -> bool:
        """Check if a plugin has required permissions."""
        if name not in self.installed_plugins:
            return False

        installed = self.installed_plugins[name]
        plugin_permissions = installed.manifest.get_required_permissions()
        return required_permissions.issubset(plugin_permissions)

    def get_enabled_plugins_by_type(self, plugin_type: PluginType) -> List[InstalledPlugin]:
        """Get all enabled plugins of a specific type."""
        return [
            p for p in self.installed_plugins.values()
            if p.status == PluginStatus.ENABLED and p.manifest.plugin_type == plugin_type
        ]