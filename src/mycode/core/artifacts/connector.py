"""MCP connector for artifacts - enables live data from MCP servers in artifacts."""

import asyncio
import json
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Callable, Awaitable
from pathlib import Path
from enum import Enum
from datetime import datetime
import weakref


class ConnectorStatus(str, Enum):
    """MCP connector status."""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    ERROR = "error"


@dataclass
class MCPResourceSubscription:
    """Subscription to an MCP resource with auto-refresh."""
    uri: str
    callback: Callable[[Any], Awaitable[None]]
    interval: float = 5.0  # seconds
    last_update: Optional[datetime] = None
    last_data: Any = None
    task: Optional[asyncio.Task] = None
    active: bool = True


@dataclass
class MCPToolBinding:
    """Binding between an artifact action and an MCP tool."""
    tool_name: str
    arguments: Dict[str, Any]
    artifact_id: str
    action_id: str
    description: str = ""


class MCPArtifactConnector:
    """Connects artifacts to MCP servers for live data and interactions."""

    def __init__(self, mcp_client):
        self.mcp_client = mcp_client
        self.subscriptions: Dict[str, MCPResourceSubscription] = {}
        self.tool_bindings: Dict[str, MCPToolBinding] = {}
        self.status = ConnectorStatus.DISCONNECTED
        self._status_callbacks: List[Callable[[ConnectorStatus], None]] = []
        self._cleanup_tasks: List[asyncio.Task] = []

    def add_status_callback(self, callback: Callable[[ConnectorStatus], None]):
        """Add a callback for status changes."""
        self._status_callbacks.append(callback)

    def _set_status(self, status: ConnectorStatus):
        """Update connector status."""
        self.status = status
        for callback in self._status_callbacks:
            try:
                callback(status)
            except Exception:
                pass

    async def connect(self):
        """Connect to MCP servers."""
        self._set_status(ConnectorStatus.CONNECTING)
        try:
            # The MCP client handles its own connections
            # We just verify it's working
            servers = self.mcp_client.list_servers()
            if servers:
                self._set_status(ConnectorStatus.CONNECTED)
            else:
                self._set_status(ConnectorStatus.DISCONNECTED)
        except Exception as e:
            self._set_status(ConnectorStatus.ERROR)

    async def disconnect(self):
        """Disconnect and clean up."""
        # Stop all subscriptions
        for sub_id, subscription in list(self.subscriptions.items()):
            await self.unsubscribe(sub_id)

        # Cancel cleanup tasks
        for task in self._cleanup_tasks:
            task.cancel()
        self._cleanup_tasks.clear()

        self._set_status(ConnectorStatus.DISCONNECTED)

    # Resource subscriptions for live data
    async def subscribe(
        self,
        uri: str,
        callback: Callable[[Any], Awaitable[None]],
        interval: float = 5.0,
        sub_id: str = None
    ) -> str:
        """Subscribe to an MCP resource with auto-refresh."""
        import uuid
        if sub_id is None:
            sub_id = f"sub_{str(uuid.uuid4())[:8]}"

        subscription = MCPResourceSubscription(
            uri=uri,
            callback=callback,
            interval=interval
        )

        # Initial fetch
        try:
            data = await self.mcp_client.read_resource(uri)
            subscription.last_data = data
            subscription.last_update = datetime.now()
            await callback(data)
        except Exception as e:
            # Still create subscription, will retry on interval
            pass

        # Start background refresh task
        async def refresh_loop():
            while subscription.active:
                await asyncio.sleep(subscription.interval)
                if not subscription.active:
                    break
                try:
                    data = await self.mcp_client.read_resource(uri)
                    # Only callback if data changed
                    if data != subscription.last_data:
                        subscription.last_data = data
                        subscription.last_update = datetime.now()
                        await callback(data)
                except Exception:
                    pass  # Silently retry

        subscription.task = asyncio.create_task(refresh_loop())
        self._cleanup_tasks.append(subscription.task)
        self.subscriptions[sub_id] = subscription

        return sub_id

    async def unsubscribe(self, sub_id: str) -> bool:
        """Unsubscribe from a resource."""
        if sub_id in self.subscriptions:
            subscription = self.subscriptions[sub_id]
            subscription.active = False
            if subscription.task:
                subscription.task.cancel()
                try:
                    await subscription.task
                except asyncio.CancelledError:
                    pass
            del self.subscriptions[sub_id]
            return True
        return False

    def get_subscription(self, sub_id: str) -> Optional[MCPResourceSubscription]:
        """Get a subscription by ID."""
        return self.subscriptions.get(sub_id)

    def list_subscriptions(self) -> List[MCPResourceSubscription]:
        """List all active subscriptions."""
        return list(self.subscriptions.values())

    # Tool bindings for interactive artifacts
    def bind_tool(
        self,
        artifact_id: str,
        action_id: str,
        tool_name: str,
        arguments: Dict[str, Any],
        description: str = ""
    ) -> str:
        """Bind an artifact action to an MCP tool."""
        binding_id = f"{artifact_id}_{action_id}"
        binding = MCPToolBinding(
            tool_name=tool_name,
            arguments=arguments,
            artifact_id=artifact_id,
            action_id=action_id,
            description=description
        )
        self.tool_bindings[binding_id] = binding
        return binding_id

    def unbind_tool(self, artifact_id: str, action_id: str) -> bool:
        """Unbind an artifact action from an MCP tool."""
        binding_id = f"{artifact_id}_{action_id}"
        if binding_id in self.tool_bindings:
            del self.tool_bindings[binding_id]
            return True
        return False

    async def execute_binding(self, artifact_id: str, action_id: str) -> Any:
        """Execute a tool binding."""
        binding_id = f"{artifact_id}_{action_id}"
        binding = self.tool_bindings.get(binding_id)
        if not binding:
            raise ValueError(f"No binding found for {artifact_id}.{action_id}")

        return await self.mcp_client.call_tool(binding.tool_name, binding.arguments)

    def get_binding(self, artifact_id: str, action_id: str) -> Optional[MCPToolBinding]:
        """Get a tool binding."""
        binding_id = f"{artifact_id}_{action_id}"
        return self.tool_bindings.get(binding_id)

    def list_bindings(self) -> List[MCPToolBinding]:
        """List all tool bindings."""
        return list(self.tool_bindings.values())

    # Prompt templates
    async def render_prompt(self, prompt_name: str, arguments: Dict[str, Any]) -> str:
        """Render an MCP prompt template."""
        result = await self.mcp_client.get_prompt(prompt_name, arguments)
        if isinstance(result, dict) and "messages" in result:
            # Format as string
            messages = result["messages"]
            return "\n".join(f"[{m.get('role', 'unknown')}] {m.get('content', '')}" for m in messages)
        return str(result)

    # Artifact creation helpers
    def create_live_markdown_artifact(
        self,
        title: str,
        resource_uri: str,
        refresh_interval: float = 5.0,
        format_fn: Callable[[Any], str] = None
    ):
        """Create an artifact that displays live data from an MCP resource."""
        from .renderer import ArtifactManager, Artifact, ArtifactType

        # This would be created with an ArtifactManager
        # Return a factory function
        def create_artifact(manager: ArtifactManager) -> Artifact:
            artifact = manager.create_artifact(
                ArtifactType.MARKDOWN,
                title,
                "Loading...",
                metadata={
                    "live": True,
                    "resource_uri": resource_uri,
                    "refresh_interval": refresh_interval
                }
            )

            # Subscribe to resource
            async def update_callback(data):
                content = format_fn(data) if format_fn else str(data)
                # Update artifact content (would need artifact reference)
                artifact.content = content
                # Re-render would happen externally

            # Note: Actual subscription would be managed externally
            # This is a helper for the pattern
            artifact.metadata["_subscription_factory"] = lambda: self.subscribe(
                resource_uri, update_callback, refresh_interval
            )

            return artifact

        return create_artifact

    def create_interactive_artifact(
        self,
        title: str,
        tool_name: str,
        tool_arguments: Dict[str, Any],
        action_id: str = "execute",
        description: str = ""
    ):
        """Create an artifact with an interactive MCP tool call."""
        from .renderer import ArtifactManager, Artifact, ArtifactType

        def create_artifact(manager: ArtifactManager) -> Artifact:
            artifact = manager.create_artifact(
                ArtifactType.PANEL,
                title,
                f"Action: {description or tool_name}\nPress Enter to execute",
                metadata={
                    "interactive": True,
                    "tool_name": tool_name,
                    "tool_arguments": tool_arguments,
                    "action_id": action_id,
                    "_binding_factory": lambda aid: self.bind_tool(
                        aid, action_id, tool_name, tool_arguments, description
                    )
                }
            )
            return artifact

        return create_artifact


class ArtifactDataSource:
    """Base class for artifact data sources."""

    async def fetch(self) -> Any:
        """Fetch data from the source."""
        raise NotImplementedError


class MCPResourceDataSource(ArtifactDataSource):
    """Data source from an MCP resource."""

    def __init__(self, connector: MCPArtifactConnector, uri: str):
        self.connector = connector
        self.uri = uri

    async def fetch(self) -> Any:
        return await self.connector.mcp_client.read_resource(self.uri)


class MCPToolDataSource(ArtifactDataSource):
    """Data source from an MCP tool call."""

    def __init__(self, connector: MCPArtifactConnector, tool_name: str, arguments: Dict[str, Any]):
        self.connector = connector
        self.tool_name = tool_name
        self.arguments = arguments

    async def fetch(self) -> Any:
        return await self.connector.mcp_client.call_tool(self.tool_name, self.arguments)


class StaticDataSource(ArtifactDataSource):
    """Static data source."""

    def __init__(self, data: Any):
        self.data = data

    async def fetch(self) -> Any:
        return self.data


class CompositeDataSource(ArtifactDataSource):
    """Composite data source combining multiple sources."""

    def __init__(self, sources: List[ArtifactDataSource], combiner: Callable[[List[Any]], Any] = None):
        self.sources = sources
        self.combiner = combiner or (lambda results: results)

    async def fetch(self) -> Any:
        results = []
        for source in self.sources:
            results.append(await source.fetch())
        return self.combiner(results)


class LiveArtifactUpdater:
    """Manages live updates for artifacts."""

    def __init__(self, connector: MCPArtifactConnector):
        self.connector = connector
        self.updaters: Dict[str, asyncio.Task] = {}

    async def start_updates(
        self,
        artifact_id: str,
        data_source: ArtifactDataSource,
        update_callback: Callable[[Any], Awaitable[None]],
        interval: float = 5.0
    ):
        """Start live updates for an artifact."""
        if artifact_id in self.updaters:
            await self.stop_updates(artifact_id)

        async def update_loop():
            while True:
                await asyncio.sleep(interval)
                try:
                    data = await data_source.fetch()
                    await update_callback(data)
                except Exception as e:
                    # Log error but continue
                    pass

        task = asyncio.create_task(update_loop())
        self.updaters[artifact_id] = task

    async def stop_updates(self, artifact_id: str):
        """Stop live updates for an artifact."""
        if artifact_id in self.updaters:
            task = self.updaters[artifact_id]
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
            del self.updaters[artifact_id]

    async def stop_all(self):
        """Stop all live updates."""
        for artifact_id in list(self.updaters.keys()):
            await self.stop_updates(artifact_id)