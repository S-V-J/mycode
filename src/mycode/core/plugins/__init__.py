"""Plugin system for MyCode - extensible plugin architecture."""

from .manifest import (
    PluginManifest,
    PluginDependency,
    PluginEntryPoint,
    PluginType,
    DependencyType,
    PluginLockFile,
    PluginLockEntry,
)

from .marketplace import (
    MarketplaceManager,
    MarketplaceConfig,
    MarketplacePlugin,
    MarketplaceType,
)

from .manager import (
    PluginManager,
    InstalledPlugin,
    PluginStatus,
)

from .loader import (
    PluginLoader,
    LoadedPlugin,
    PluginSandbox,
    SkillPluginInterface,
    ToolPluginInterface,
    MCPServerPluginInterface,
    ThemePluginInterface,
    HookPluginInterface,
    LSPPluginInterface,
    MonitorPluginInterface,
    ArtifactPluginInterface,
    ChannelPluginInterface,
)

# Global instances
_plugin_manager: PluginManager = None
_skill_registry = None
_skill_executor = None
_artifact_manager = None
_channel_server = None
_permission_relay = None


def get_plugin_manager(config_dir: Path, project_dir: Path = None) -> PluginManager:
    """Get or create the global plugin manager."""
    global _plugin_manager
    if _plugin_manager is None:
        _plugin_manager = PluginManager(config_dir, project_dir)
    return _plugin_manager


def get_marketplace_manager(config_dir: Path) -> MarketplaceManager:
    """Get the marketplace manager from the plugin manager."""
    manager = get_plugin_manager(config_dir)
    return manager.marketplace_manager


__all__ = [
    # Manifest
    "PluginManifest",
    "PluginDependency",
    "PluginEntryPoint",
    "PluginType",
    "DependencyType",
    "PluginLockFile",
    "PluginLockEntry",
    # Marketplace
    "MarketplaceManager",
    "MarketplaceConfig",
    "MarketplacePlugin",
    "MarketplaceType",
    # Manager
    "PluginManager",
    "InstalledPlugin",
    "PluginStatus",
    # Loader
    "PluginLoader",
    "LoadedPlugin",
    "PluginSandbox",
    # Interfaces
    "SkillPluginInterface",
    "ToolPluginInterface",
    "MCPServerPluginInterface",
    "ThemePluginInterface",
    "HookPluginInterface",
    "LSPPluginInterface",
    "MonitorPluginInterface",
    "ArtifactPluginInterface",
    "ChannelPluginInterface",
    # Helpers
    "get_plugin_manager",
    "get_marketplace_manager",
]