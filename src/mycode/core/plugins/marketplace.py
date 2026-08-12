"""Plugin marketplace protocol for discovering and installing plugins."""

import json
import hashlib
import asyncio
import subprocess
import tempfile
import shutil
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Set
from pathlib import Path
from enum import Enum
from datetime import datetime
import httpx
import semver

from .manifest import (
    PluginManifest, PluginDependency, PluginType, DependencyType,
    PluginLockFile, PluginLockEntry
)


class MarketplaceType(str, Enum):
    """Types of plugin marketplaces."""
    GITHUB = "github"
    LOCAL = "local"
    NPM = "npm"
    CUSTOM = "custom"


@dataclass
class MarketplaceConfig:
    """Marketplace configuration."""
    name: str
    type: MarketplaceType
    url: str  # Base URL or GitHub org/repo
    auth_token: Optional[str] = None
    priority: int = 0  # Higher priority = checked first
    enabled: bool = True


@dataclass
class MarketplacePlugin:
    """Plugin information from a marketplace."""
    name: str
    version: str
    description: str
    author: str
    repository: str
    marketplace: str
    download_url: str
    checksum: str
    dependencies: List[PluginDependency] = field(default_factory=list)
    manifest: Optional[PluginManifest] = None


class MarketplaceManager:
    """Manages plugin marketplaces and plugin discovery."""

    def __init__(self, config_dir: Path):
        self.config_dir = config_dir
        self.marketplaces: Dict[str, MarketplaceConfig] = {}
        self._cache: Dict[str, List[MarketplacePlugin]] = {}
        self._load_config()

    def _load_config(self):
        """Load marketplace configurations."""
        config_file = self.config_dir / "marketplaces.json"
        if config_file.exists():
            try:
                with open(config_file, 'r') as f:
                    data = json.load(f)
                    for mp_data in data.get("marketplaces", []):
                        config = MarketplaceConfig(
                            name=mp_data["name"],
                            type=MarketplaceType(mp_data["type"]),
                            url=mp_data["url"],
                            auth_token=mp_data.get("auth_token"),
                            priority=mp_data.get("priority", 0),
                            enabled=mp_data.get("enabled", True)
                        )
                        self.marketplaces[config.name] = config
            except Exception as e:
                print(f"Warning: Failed to load marketplace config: {e}")

    def save_config(self):
        """Save marketplace configurations."""
        config_file = self.config_dir / "marketplaces.json"
        config_file.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "marketplaces": [
                {
                    "name": mp.name,
                    "type": mp.type.value,
                    "url": mp.url,
                    "auth_token": mp.auth_token,
                    "priority": mp.priority,
                    "enabled": mp.enabled
                }
                for mp in self.marketplaces.values()
            ]
        }
        with open(config_file, 'w') as f:
            json.dump(data, f, indent=2)

    def add_marketplace(self, config: MarketplaceConfig) -> bool:
        """Add a marketplace."""
        if config.name in self.marketplaces:
            return False
        self.marketplaces[config.name] = config
        self.save_config()
        return True

    def remove_marketplace(self, name: str) -> bool:
        """Remove a marketplace."""
        if name in self.marketplaces:
            del self.marketplaces[name]
            self.save_config()
            return True
        return False

    def list_marketplaces(self) -> List[MarketplaceConfig]:
        """List all marketplaces."""
        return sorted(self.marketplaces.values(), key=lambda m: -m.priority)

    async def search_plugins(self, query: str = "", marketplace: str = None) -> List[MarketplacePlugin]:
        """Search for plugins across marketplaces."""
        results = []

        marketplaces_to_search = [self.marketplaces[marketplace]] if marketplace else self.list_marketplaces()

        for mp in marketplaces_to_search:
            if not mp.enabled:
                continue

            try:
                if mp.type == MarketplaceType.GITHUB:
                    plugins = await self._search_github(mp, query)
                elif mp.type == MarketplaceType.LOCAL:
                    plugins = await self._search_local(mp, query)
                elif mp.type == MarketplaceType.NPM:
                    plugins = await self._search_npm(mp, query)
                else:
                    plugins = []

                results.extend(plugins)
            except Exception as e:
                print(f"Warning: Search failed for marketplace {mp.name}: {e}")

        # Deduplicate by name@version
        seen = set()
        unique = []
        for p in results:
            key = f"{p.name}@{p.version}"
            if key not in seen:
                seen.add(key)
                unique.append(p)

        return unique

    async def _search_github(self, marketplace: MarketplaceConfig, query: str) -> List[MarketplacePlugin]:
        """Search GitHub marketplace."""
        url = f"https://api.github.com/search/repositories"
        params = {
            "q": f"{query} mycode-plugin in:name,description,topics" if query else "mycode-plugin in:topics",
            "sort": "stars",
            "order": "desc",
            "per_page": 30
        }
        headers = {}
        if marketplace.auth_token:
            headers["Authorization"] = f"token {marketplace.auth_token}"

        async with httpx.AsyncClient() as client:
            response = await client.get(url, params=params, headers=headers)
            response.raise_for_status()
            data = response.json()

        plugins = []
        for repo in data.get("items", []):
            manifest = await self._fetch_github_manifest(marketplace, repo["full_name"])
            if manifest:
                plugins.append(MarketplacePlugin(
                    name=manifest.name,
                    version=manifest.version,
                    description=manifest.description,
                    author=manifest.author,
                    repository=repo["html_url"],
                    marketplace=marketplace.name,
                    download_url=f"https://github.com/{repo['full_name']}/archive/refs/heads/main.zip",
                    checksum="",
                    dependencies=manifest.dependencies,
                    manifest=manifest
                ))

        return plugins

    async def _fetch_github_manifest(self, marketplace: MarketplaceConfig, repo: str) -> Optional[PluginManifest]:
        """Fetch plugin.json from a GitHub repository."""
        url = f"https://raw.githubusercontent.com/{repo}/main/plugin.json"
        headers = {}
        if marketplace.auth_token:
            headers["Authorization"] = f"token {marketplace.auth_token}"

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(url, headers=headers)
                if response.status_code == 200:
                    data = response.json()
                    return PluginManifest.from_dict(data)
        except Exception:
            pass
        return None

    async def _search_local(self, marketplace: MarketplaceConfig, query: str) -> List[MarketplacePlugin]:
        """Search local directory for plugins."""
        base_path = Path(marketplace.url).expanduser()
        if not base_path.exists():
            return []

        plugins = []
        for plugin_dir in base_path.iterdir():
            if not plugin_dir.is_dir():
                continue

            manifest_file = plugin_dir / "plugin.json"
            if not manifest_file.exists():
                continue

            try:
                manifest = PluginManifest.from_file(manifest_file)
                if query and query.lower() not in manifest.name.lower() and query.lower() not in manifest.description.lower():
                    continue

                plugins.append(MarketplacePlugin(
                    name=manifest.name,
                    version=manifest.version,
                    description=manifest.description,
                    author=manifest.author,
                    repository=str(plugin_dir),
                    marketplace=marketplace.name,
                    download_url=str(plugin_dir),
                    checksum="",
                    dependencies=manifest.dependencies,
                    manifest=manifest
                ))
            except Exception:
                pass

        return plugins

    async def _search_npm(self, marketplace: MarketplaceConfig, query: str) -> List[MarketplacePlugin]:
        """Search npm registry for plugins."""
        url = "https://registry.npmjs.org/-/v1/search"
        params = {
            "text": f"{query} mycode-plugin" if query else "mycode-plugin",
            "size": 30
        }

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(url, params=params)
                response.raise_for_status()
                data = response.json()

            plugins = []
            for pkg in data.get("objects", []):
                pkg_data = pkg["package"]
                name = pkg_data.get("name", "")
                if not name.startswith("mycode-plugin-"):
                    continue

                version = pkg_data.get("version", "")
                description = pkg_data.get("description", "")
                author = pkg_data.get("author", {}).get("name", "") if isinstance(pkg_data.get("author"), dict) else str(pkg_data.get("author", ""))
                repository = pkg_data.get("repository", {}).get("url", "") if isinstance(pkg_data.get("repository"), dict) else str(pkg_data.get("repository", ""))

                manifest_url = f"https://registry.npmjs.org/{name}/{version}"
                manifest = await self._fetch_npm_manifest(manifest_url)
                if manifest:
                    plugins.append(MarketplacePlugin(
                        name=manifest.name,
                        version=manifest.version,
                        description=manifest.description,
                        author=manifest.author,
                        repository=repository,
                        marketplace=marketplace.name,
                        download_url=f"https://registry.npmjs.org/{name}/-/{name}-{version}.tgz",
                        checksum="",
                        dependencies=manifest.dependencies,
                        manifest=manifest
                    ))
            return plugins
        except Exception:
            return []

    async def _fetch_npm_manifest(self, url: str) -> Optional[PluginManifest]:
        """Fetch plugin manifest from npm package."""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(url)
                if response.status_code == 200:
                    data = response.json()
                    if "mycode" in data:
                        return PluginManifest.from_dict(data["mycode"])
        except Exception:
            pass
        return None

    async def get_plugin_versions(self, name: str, marketplace: str = None) -> List[str]:
        """Get all available versions of a plugin."""
        results = await self.search_plugins(query=name, marketplace=marketplace)
        versions = set()
        for p in results:
            if p.name == name:
                versions.add(p.version)
        return sorted(list(versions), key=lambda v: semver.VersionInfo.parse(v), reverse=True)

    async def download_plugin(self, plugin: MarketplacePlugin, dest: Path) -> Path:
        """Download a plugin to destination directory."""
        dest.mkdir(parents=True, exist_ok=True)

        if plugin.download_url.endswith(".zip"):
            # GitHub zip download
            async with httpx.AsyncClient() as client:
                response = await client.get(plugin.download_url)
                response.raise_for_status()

                import zipfile
                import io
                with zipfile.ZipFile(io.BytesIO(response.content)) as zf:
                    zf.extractall(dest)

                extracted = list(dest.iterdir())
                if len(extracted) == 1 and extracted[0].is_dir():
                    # Move contents up one level
                    for item in extracted[0].iterdir():
                        shutil.move(str(item), str(dest / item.name))
                    shutil.rmtree(extracted[0])

        elif plugin.download_url.endswith(".tgz") or plugin.download_url.endswith(".tar.gz"):
            # npm tarball
            async with httpx.AsyncClient() as client:
                response = await client.get(plugin.download_url)
                response.raise_for_status()

                import tarfile
                import io
                with tarfile.open(fileobj=io.BytesIO(response.content), mode="r:gz") as tf:
                    tf.extractall(dest)

                extracted = list(dest.iterdir())
                if len(extracted) == 1 and extracted[0].is_dir():
                    for item in extracted[0].iterdir():
                        shutil.move(str(item), str(dest / item.name))
                    shutil.rmtree(extracted[0])

        else:
            # Local directory - copy
            src = Path(plugin.download_url)
            if src.exists():
                for item in src.iterdir():
                    if item.is_dir():
                        shutil.copytree(item, dest / item.name, dirs_exist_ok=True)
                    else:
                        shutil.copy2(item, dest)

        # Verify manifest exists
        manifest_file = dest / "plugin.json"
        if not manifest_file.exists():
            raise FileNotFoundError(f"plugin.json not found in downloaded plugin")

        # Compute checksum
        checksum = self._compute_checksum(dest)
        return dest

    def _compute_checksum(self, path: Path) -> str:
        """Compute SHA256 checksum of plugin directory."""
        hasher = hashlib.sha256()
        for file_path in sorted(path.rglob("*")):
            if file_path.is_file():
                hasher.update(file_path.read_bytes())
        return hasher.hexdigest()