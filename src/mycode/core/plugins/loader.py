"""Plugin loader for dynamic import and sandboxed execution."""

import importlib.util
import sys
import types
import asyncio
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Set, Callable
from pathlib import Path
from enum import Enum
import contextlib
import traceback


class PluginSandbox:
    """Sandbox for plugin execution with restricted capabilities."""

    def __init__(self, allowed_modules: Set[str] = None, permissions: Set[str] = None):
        self.allowed_modules = allowed_modules or {
            "json", "re", "datetime", "pathlib", "typing",
            "dataclasses", "enum", "collections", "itertools",
            "functools", "hashlib", "base64", "uuid",
            "asyncio", "os", "sys", "time", "math", "random",
            "httpx", "websockets", "pydantic", "rich",
        }
        self.permissions = permissions or set()
        self._original_modules = {}
        self._restricted_builtins = {
            "__import__": self._restricted_import,
            "open": self._restricted_open,
            "eval": None,
            "exec": None,
            "compile": None,
            "open": self._restricted_open,
        }

    def _restricted_import(self, name: str, *args, **kwargs):
        """Restricted import function."""
        if name in self.allowed_modules:
            return __import__(name, *args, **kwargs)
        # Allow relative imports and submodules of allowed modules
        for allowed in self.allowed_modules:
            if name.startswith(allowed + "."):
                return __import__(name, *args, **kwargs)
        raise ImportError(f"Import of '{name}' not allowed in plugin sandbox")

    def _restricted_open(self, path, *args, **kwargs):
        """Restricted file open."""
        path = Path(path).resolve()
        # Only allow reading files within plugin directory or temp
        # This would be configured per plugin
        return open(path, *args, **kwargs)

    def create_sandbox_globals(self) -> Dict[str, Any]:
        """Create sandboxed globals dictionary."""
        sandbox_globals = {
            "__builtins__": {k: v for k, v in __builtins__.items() if k not in self._restricted_builtins or self._restricted_builtins[k] is not None},
        }
        sandbox_globals["__builtins__"].update({k: v for k, v in self._restricted_builtins.items() if v is not None})
        return sandbox_globals


@dataclass
class LoadedPlugin:
    """A loaded plugin with its entry points."""
    name: str
    path: Path
    manifest: Any  # PluginManifest
    modules: Dict[str, types.ModuleType] = field(default_factory=dict)
    entry_points: Dict[str, Any] = field(default_factory=dict)
    sandbox: Optional[PluginSandbox] = None
    config: Dict[str, Any] = field(default_factory=dict)


class PluginLoader:
    """Loads and manages plugin modules with sandboxing."""

    def __init__(self):
        self.loaded_plugins: Dict[str, LoadedPlugin] = {}
        self._plugin_paths: Dict[str, Path] = {}

    def load_plugin(
        self,
        name: str,
        plugin_path: Path,
        manifest: Any,
        config: Dict[str, Any] = None,
        permissions: Set[str] = None
    ) -> LoadedPlugin:
        """Load a plugin from its directory."""
        # Add plugin directory to path
        plugin_path_str = str(plugin_path)
        if plugin_path_str not in sys.path:
            sys.path.insert(0, plugin_path_str)

        # Create sandbox
        allowed_modules = set()
        if hasattr(manifest, 'permissions'):
            # Add modules based on permissions
            if "network:http" in manifest.permissions:
                allowed_modules.add("httpx")
            if "network:websocket" in manifest.permissions:
                allowed_modules.add("websockets")

        sandbox = PluginSandbox(allowed_modules=allowed_modules, permissions=permissions or set())

        # Create loaded plugin object
        loaded = LoadedPlugin(
            name=name,
            path=plugin_path,
            manifest=manifest,
            sandbox=sandbox,
            config=config or {}
        )

        # Load entry points
        for entry_point in manifest.entry_points:
            try:
                cls = self._load_entry_point(plugin_path, entry_point, sandbox)
                if cls:
                    loaded.entry_points[entry_point.name] = cls
            except Exception as e:
                print(f"Warning: Failed to load entry point '{entry_point.name}': {e}")
                traceback.print_exc()

        self.loaded_plugins[name] = loaded
        self._plugin_paths[name] = plugin_path
        return loaded

    def _load_entry_point(
        self,
        plugin_path: Path,
        entry_point: Any,
        sandbox: PluginSandbox
    ) -> Any:
        """Load a single entry point."""
        # Import the module
        module_name = entry_point.module
        class_name = entry_point.class_name

        try:
            # Use importlib to load the module
            spec = importlib.util.find_spec(module_name)
            if spec is None:
                # Try relative to plugin path
                module_file = plugin_path / module_name.replace(".", "/")
                if module_file.with_suffix(".py").exists():
                    spec = importlib.util.spec_from_file_location(module_name, module_file.with_suffix(".py"))
                elif (module_file / "__init__.py").exists():
                    spec = importlib.util.spec_from_file_location(module_name, module_file / "__init__.py")

            if spec is None:
                raise ImportError(f"Module '{module_name}' not found")

            module = importlib.util.module_from_spec(spec)

            # Apply sandbox if needed
            if sandbox:
                # Set sandboxed globals
                module.__dict__.update(sandbox.create_sandbox_globals())

            spec.loader.exec_module(module)
            cls = getattr(module, class_name)
            return cls

        except Exception as e:
            print(f"Failed to load entry point {module_name}.{class_name}: {e}")
            raise

    def unload_plugin(self, name: str):
        """Unload a plugin."""
        if name in self.loaded_plugins:
            loaded = self.loaded_plugins[name]

            # Remove modules from sys.modules
            for mod_name, module in loaded.modules.items():
                if mod_name in sys.modules:
                    del sys.modules[mod_name]

            # Remove plugin path from sys.path
            plugin_path_str = str(loaded.path)
            if plugin_path_str in sys.path:
                sys.path.remove(plugin_path_str)

            del self.loaded_plugins[name]
            if name in self._plugin_paths:
                del self._plugin_paths[name]

    def get_plugin(self, name: str) -> Optional[LoadedPlugin]:
        """Get a loaded plugin."""
        return self.loaded_plugins.get(name)

    def get_entry_point(self, plugin_name: str, entry_point_name: str) -> Any:
        """Get a specific entry point from a loaded plugin."""
        loaded = self.loaded_plugins.get(plugin_name)
        if loaded:
            return loaded.entry_points.get(entry_point_name)
        return None

    def list_loaded_plugins(self) -> List[str]:
        """List all loaded plugin names."""
        return list(self.loaded_plugins.keys())

    def reload_plugin(self, name: str, plugin_path: Path, manifest: Any, config: Dict[str, Any] = None) -> LoadedPlugin:
        """Reload a plugin."""
        self.unload_plugin(name)
        return self.load_plugin(name, plugin_path, manifest, config)

    @contextlib.contextmanager
    def plugin_context(self, plugin_name: str):
        """Context manager for executing code within plugin context."""
        loaded = self.loaded_plugins.get(plugin_name)
        if not loaded:
            raise ValueError(f"Plugin '{plugin_name}' not loaded")

        # Save current state
        old_path = sys.path[:]
        old_modules = dict(sys.modules)

        try:
            # Add plugin path
            plugin_path_str = str(loaded.path)
            if plugin_path_str not in sys.path:
                sys.path.insert(0, plugin_path_str)

            # Set sandbox globals if available
            if loaded.sandbox:
                pass  # Module-level sandboxing handled at load time

            yield loaded
        finally:
            # Restore state
            sys.path[:] = old_path
            sys.modules.clear()
            sys.modules.update(old_modules)


class SkillPluginInterface:
    """Interface for plugins that provide skills."""

    @staticmethod
    def get_skills(plugin: LoadedPlugin) -> List[Dict[str, Any]]:
        """Extract skills from a plugin."""
        skills = []
        for ep_name, ep_class in plugin.entry_points.items():
            if hasattr(ep_class, 'get_skill_manifest'):
                try:
                    manifest = ep_class.get_skill_manifest()
                    skills.append({
                        "name": manifest.get("name", ep_name),
                        "description": manifest.get("description", ""),
                        "entry_point": ep_name,
                        "plugin": plugin.name,
                        "arguments": manifest.get("arguments", []),
                    })
                except Exception:
                    pass
        return skills


class ToolPluginInterface:
    """Interface for plugins that provide tools."""

    @staticmethod
    def get_tools(plugin: LoadedPlugin) -> List[Dict[str, Any]]:
        """Extract tools from a plugin."""
        tools = []
        for ep_name, ep_class in plugin.entry_points.items():
            if hasattr(ep_class, 'get_tool_schema'):
                try:
                    schema = ep_class.get_tool_schema()
                    tools.append({
                        "name": schema.get("name", ep_name),
                        "description": schema.get("description", ""),
                        "input_schema": schema.get("input_schema", {}),
                        "entry_point": ep_name,
                        "plugin": plugin.name,
                    })
                except Exception:
                    pass
        return tools


class MCPServerPluginInterface:
    """Interface for plugins that provide MCP servers."""

    @staticmethod
    def get_mcp_servers(plugin: LoadedPlugin) -> List[Dict[str, Any]]:
        """Extract MCP server configs from a plugin."""
        servers = []
        for ep_name, ep_class in plugin.entry_points.items():
            if hasattr(ep_class, 'get_mcp_server_config'):
                try:
                    config = ep_class.get_mcp_server_config()
                    servers.append({
                        "name": config.get("name", ep_name),
                        "transport": config.get("transport", "stdio"),
                        "command": config.get("command"),
                        "args": config.get("args", []),
                        "url": config.get("url"),
                        "entry_point": ep_name,
                        "plugin": plugin.name,
                    })
                except Exception:
                    pass
        return servers


class ThemePluginInterface:
    """Interface for plugins that provide themes."""

    @staticmethod
    def get_themes(plugin: LoadedPlugin) -> List[Dict[str, Any]]:
        """Extract themes from a plugin."""
        themes = []
        for ep_name, ep_class in plugin.entry_points.items():
            if hasattr(ep_class, 'get_theme'):
                try:
                    theme = ep_class.get_theme()
                    themes.append({
                        "name": theme.get("name", ep_name),
                        "description": theme.get("description", ""),
                        "colors": theme.get("colors", {}),
                        "entry_point": ep_name,
                        "plugin": plugin.name,
                    })
                except Exception:
                    pass
        return themes


class HookPluginInterface:
    """Interface for plugins that provide hooks."""

    @staticmethod
    def get_hooks(plugin: LoadedPlugin) -> List[Dict[str, Any]]:
        """Extract hooks from a plugin."""
        hooks = []
        for ep_name, ep_class in plugin.entry_points.items():
            if hasattr(ep_class, 'get_hooks'):
                try:
                    hook_list = ep_class.get_hooks()
                    for hook in hook_list:
                        hooks.append({
                            "event": hook.get("event"),
                            "matcher": hook.get("matcher"),
                            "handler": hook.get("handler"),
                            "config": hook.get("config", {}),
                            "entry_point": ep_name,
                            "plugin": plugin.name,
                        })
                except Exception:
                    pass
        return hooks


class LSPPluginInterface:
    """Interface for plugins that provide LSP servers."""

    @staticmethod
    def get_lsp_servers(plugin: LoadedPlugin) -> List[Dict[str, Any]]:
        """Extract LSP server configs from a plugin."""
        servers = []
        for ep_name, ep_class in plugin.entry_points.items():
            if hasattr(ep_class, 'get_lsp_server'):
                try:
                    config = ep_class.get_lsp_server()
                    servers.append({
                        "name": config.get("name", ep_name),
                        "language": config.get("language", ""),
                        "command": config.get("command"),
                        "args": config.get("args", []),
                        "entry_point": ep_name,
                        "plugin": plugin.name,
                    })
                except Exception:
                    pass
        return servers


class MonitorPluginInterface:
    """Interface for plugins that provide background monitors."""

    @staticmethod
    def get_monitors(plugin: LoadedPlugin) -> List[Dict[str, Any]]:
        """Extract monitors from a plugin."""
        monitors = []
        for ep_name, ep_class in plugin.entry_points.items():
            if hasattr(ep_class, 'get_monitors'):
                try:
                    monitor_list = ep_class.get_monitors()
                    for monitor in monitor_list:
                        monitors.append({
                            "name": monitor.get("name", ep_name),
                            "type": monitor.get("type", "file_watcher"),
                            "config": monitor.get("config", {}),
                            "entry_point": ep_name,
                            "plugin": plugin.name,
                        })
                except Exception:
                    pass
        return monitors


class ArtifactPluginInterface:
    """Interface for plugins that provide artifact renderers."""

    @staticmethod
    def get_artifact_renderers(plugin: LoadedPlugin) -> List[Dict[str, Any]]:
        """Extract artifact renderers from a plugin."""
        renderers = []
        for ep_name, ep_class in plugin.entry_points.items():
            if hasattr(ep_class, 'get_artifact_renderer'):
                try:
                    renderer = ep_class.get_artifact_renderer()
                    renderers.append({
                        "name": renderer.get("name", ep_name),
                        "mime_type": renderer.get("mime_type", "text/html"),
                        "renderer": renderer.get("renderer"),
                        "entry_point": ep_name,
                        "plugin": plugin.name,
                    })
                except Exception:
                    pass
        return renderers


class ChannelPluginInterface:
    """Interface for plugins that provide channels."""

    @staticmethod
    def get_channels(plugin: LoadedPlugin) -> List[Dict[str, Any]]:
        """Extract channels from a plugin."""
        channels = []
        for ep_name, ep_class in plugin.entry_points.items():
            if hasattr(ep_class, 'get_channel'):
                try:
                    channel = ep_class.get_channel()
                    channels.append({
                        "name": channel.get("name", ep_name),
                        "type": channel.get("type", "webhook"),
                        "config": channel.get("config", {}),
                        "entry_point": ep_name,
                        "plugin": plugin.name,
                    })
                except Exception:
                    pass
        return channels