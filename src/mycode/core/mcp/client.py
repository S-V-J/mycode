"""MCP (Model Context Protocol) client implementation for MyCode."""

import json
import asyncio
import uuid
import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, AsyncGenerator, Union
from pathlib import Path
from enum import Enum
from abc import ABC, abstractmethod
import httpx
import websockets
import subprocess
import asyncio.subprocess
from rich.console import Console

console = Console()


class MCPTransportType(str, Enum):
    """MCP transport types."""
    HTTP = "http"
    SSE = "sse"
    STDIO = "stdio"
    WEBSOCKET = "websocket"


class MCPMessageType(str, Enum):
    """MCP message types."""
    REQUEST = "request"
    RESPONSE = "response"
    NOTIFICATION = "notification"
    ERROR = "error"


@dataclass
class MCPMessage:
    """MCP message structure."""
    jsonrpc: str = "2.0"
    id: Optional[Union[str, int]] = None
    method: Optional[str] = None
    params: Optional[Dict[str, Any]] = None
    result: Optional[Any] = None
    error: Optional[Dict[str, Any]] = None


@dataclass
class MCPServerConfig:
    """MCP server configuration."""
    name: str
    transport: str  # "http", "sse", "stdio", "websocket"
    url: Optional[str] = None  # For HTTP/SSE/WebSocket
    command: Optional[str] = None  # For stdio
    args: List[str] = field(default_factory=list)
    env: Dict[str, str] = field(default_factory=dict)
    auth: Optional[Dict[str, str]] = None  # API key, bearer token, etc.
    enabled: bool = True


@dataclass
class MCPTool:
    """MCP tool definition."""
    name: str
    description: str
    input_schema: Dict[str, Any]
    server_name: str


@dataclass
class MCPResource:
    """MCP resource definition."""
    uri: str
    name: str
    server_name: str
    description: Optional[str] = None
    mime_type: Optional[str] = None


@dataclass
class MCPPrompt:
    """MCP prompt template."""
    name: str
    description: str
    arguments: List[Dict[str, Any]]
    server_name: str


class MCPTransport(ABC):
    """Abstract base class for MCP transports."""

    @abstractmethod
    async def connect(self) -> None:
        """Establish connection."""
        pass

    @abstractmethod
    async def disconnect(self) -> None:
        """Close connection."""
        pass

    @abstractmethod
    async def send(self, message: MCPMessage) -> None:
        """Send a message."""
        pass

    @abstractmethod
    async def receive(self) -> Optional[MCPMessage]:
        """Receive a message."""
        pass

    @abstractmethod
    async def start_listening(self, callback: Callable[[MCPMessage], None]) -> None:
        """Start listening for messages."""
        pass


class HTTPTransport(MCPTransport):
    """HTTP/SSE transport for MCP."""

    def __init__(self, url: str, auth: Optional[Dict[str, str]] = None):
        self.url = url.rstrip('/')
        self.auth = auth or {}
        self.client: Optional[httpx.AsyncClient] = None
        self._listening = False
        self._callback: Optional[Callable[[MCPMessage], None]] = None

    async def connect(self) -> None:
        headers = {}
        if "bearer_token" in self.auth:
            headers["Authorization"] = f"Bearer {self.auth['bearer_token']}"
        if "api_key" in self.auth:
            headers["X-API-Key"] = self.auth["api_key"]

        self.client = httpx.AsyncClient(
            base_url=self.url,
            headers=headers,
            timeout=30.0
        )

    async def disconnect(self) -> None:
        if self.client:
            await self.client.aclose()
            self.client = None

    async def send(self, message: MCPMessage) -> None:
        if not self.client:
            raise RuntimeError("Not connected")
        response = await self.client.post(
            "/mcp",
            json=message.__dict__,
            headers={"Content-Type": "application/json"}
        )
        response.raise_for_status()

    async def receive(self) -> Optional[MCPMessage]:
        # For HTTP, we poll for responses
        if not self.client:
            return None
        try:
            response = await self.client.get("/mpc/events")
            if response.status_code == 200:
                data = response.json()
                return MCPMessage(**data)
        except Exception:
            pass
        return None

    async def start_listening(self, callback: Callable[[MCPMessage], None]) -> None:
        self._callback = callback
        self._listening = True
        # SSE listening would go here
        # For simplicity, we'll use polling in a background task
        asyncio.create_task(self._poll_events())

    async def _poll_events(self):
        while self._listening:
            msg = await self.receive()
            if msg and self._callback:
                self._callback(msg)
            await asyncio.sleep(1)


class StdioTransport(MCPTransport):
    """Stdio transport for MCP (local subprocess)."""

    def __init__(self, command: str, args: List[str], env: Dict[str, str] = None):
        self.command = command
        self.args = args
        self.env = env or {}
        self.process: Optional[asyncio.subprocess.Process] = None
        self._listening = False
        self._callback: Optional[Callable[[MCPMessage], None]] = None
        self._reader_task: Optional[asyncio.Task] = None

    async def connect(self) -> None:
        env = {**os.environ, **self.env}
        self.process = await asyncio.create_subprocess_exec(
            self.command, *self.args,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env
        )
        self._reader_task = asyncio.create_task(self._read_stdout())

    async def disconnect(self) -> None:
        self._listening = False
        if self._reader_task:
            self._reader_task.cancel()
        if self.process:
            self.process.terminate()
            await self.process.wait()

    async def send(self, message: MCPMessage) -> None:
        if not self.process or not self.process.stdin:
            raise RuntimeError("Process not connected")
        data = json.dumps(message.__dict__) + "\n"
        self.process.stdin.write(data.encode())
        await self.process.stdin.drain()

    async def receive(self) -> Optional[MCPMessage]:
        # Messages are received via callback
        return None

    async def start_listening(self, callback: Callable[[MCPMessage], None]) -> None:
        self._callback = callback
        self._listening = True

    async def _read_stdout(self):
        while self._listening and self.process and self.process.stdout:
            try:
                line = await self.process.stdout.readline()
                if not line:
                    break
                line = line.decode().strip()
                if line:
                    try:
                        data = json.loads(line)
                        msg = MCPMessage(**data)
                        if self._callback:
                            self._callback(msg)
                    except json.JSONDecodeError:
                        pass
            except Exception:
                break


class WebSocketTransport(MCPTransport):
    """WebSocket transport for MCP."""

    def __init__(self, url: str, auth: Optional[Dict[str, str]] = None):
        self.url = url
        self.auth = auth or {}
        self.websocket: Optional[websockets.WebSocketClientProtocol] = None
        self._listening = False
        self._callback: Optional[Callable[[MCPMessage], None]] = None
        self._reader_task: Optional[asyncio.Task] = None

    async def connect(self) -> None:
        headers = {}
        if "bearer_token" in self.auth:
            headers["Authorization"] = f"Bearer {self.auth['bearer_token']}"
        if "api_key" in self.auth:
            headers["X-API-Key"] = self.auth["api_key"]

        self.websocket = await websockets.connect(self.url, extra_headers=headers)

    async def disconnect(self) -> None:
        self._listening = False
        if self.websocket:
            await self.websocket.close()

    async def send(self, message: MCPMessage) -> None:
        if not self.websocket:
            raise RuntimeError("Not connected")
        await self.websocket.send(json.dumps(message.__dict__))

    async def receive(self) -> Optional[MCPMessage]:
        # Messages received via callback
        return None

    async def start_listening(self, callback: Callable[[MCPMessage], None]) -> None:
        self._callback = callback
        self._listening = True
        self._reader_task = asyncio.create_task(self._read_messages())

    async def _read_messages(self):
        try:
            async for message in self.websocket:
                try:
                    data = json.loads(message)
                    msg = MCPMessage(**data)
                    if self._callback:
                        self._callback(msg)
                except json.JSONDecodeError:
                    pass
        except Exception:
            pass


class MCPClient:
    """MCP client for connecting to multiple MCP servers."""

    def __init__(self, config_dir: Optional[Path] = None):
        self.config_dir = config_dir or Path.home() / ".mycode" / "mcp"
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self.servers: Dict[str, MCPServerConfig] = {}
        self.transports: Dict[str, MCPTransport] = {}
        self.tools: Dict[str, MCPTool] = {}
        self.resources: Dict[str, MCPResource] = {}
        self.prompts: Dict[str, MCPPrompt] = {}
        self._load_config()

    def _load_config(self):
        """Load MCP server configurations."""
        config_file = Path.home() / ".mycode" / "mcp.json"
        if config_file.exists():
            try:
                with open(config_file, 'r') as f:
                    data = json.load(f)
                    for server_data in data.get('servers', []):
                        config = MCPServerConfig(**server_data)
                        self.servers[config.name] = config
            except Exception as e:
                console.print(f"[yellow]Warning: Failed to load MCP config: {e}[/yellow]")

    def save_config(self):
        """Save server configurations."""
        config_file = Path.home() / ".mycode" / "mcp.json"
        config_file.parent.mkdir(parents=True, exist_ok=True)
        data = {
            'servers': [
                {
                    'name': s.name,
                    'transport': s.transport,
                    'url': s.url,
                    'command': s.command,
                    'args': s.args,
                    'env': s.env,
                    'auth': s.auth,
                    'enabled': s.enabled
                }
                for s in self.servers.values()
            ]
        }
        with open(config_file, 'w') as f:
            json.dump(data, f, indent=2)

    def add_server(self, config: MCPServerConfig) -> bool:
        """Add an MCP server."""
        if config.name in self.servers:
            return False
        self.servers[config.name] = config
        self._save_config()
        return True

    def remove_server(self, name: str) -> bool:
        """Remove an MCP server."""
        if name in self.servers:
            del self.servers[name]
            if name in self.transports:
                # Disconnect handled elsewhere
                del self.transports[name]
            self._save_config()
            return True
        return False

    def list_servers(self) -> List[MCPServerConfig]:
        """List all configured servers."""
        return list(self.servers.values())

    async def connect_server(self, name: str) -> bool:
        """Connect to an MCP server."""
        if name not in self.servers:
            return False

        config = self.servers[name]
        if not config.enabled:
            return False

        try:
            if config.transport == "http" or config.transport == "sse":
                transport = HTTPTransport(config.url or "", config.auth)
            elif config.transport == "stdio":
                transport = StdioTransport(config.command or "", config.args, config.env)
            elif config.transport == "websocket":
                transport = WebSocketTransport(config.url or "", config.auth)
            else:
                return False

            await transport.connect()
            self.transports[name] = transport

            # Start listening for messages
            await transport.start_listening(self._handle_message)

            # Initialize and discover tools/resources/prompts
            await self._initialize_server(name)

            return True
        except Exception as e:
            console.print(f"[red]Failed to connect to {name}: {e}[/red]")
            return False

    async def disconnect_server(self, name: str) -> bool:
        """Disconnect from an MCP server."""
        if name in self.transports:
            await self.transports[name].disconnect()
            del self.transports[name]
            # Clear discovered items from this server
            self.tools = {k: v for k, v in self.tools.items() if v.server_name != name}
            self.resources = {k: v for k, v in self.resources.items() if v.server_name != name}
            self.prompts = {k: v for k, v in self.prompts.items() if v.server_name != name}
            return True
        return False

    async def _initialize_server(self, name: str):
        """Initialize server and discover capabilities."""
        # Send initialize request
        await self._send_request(name, "initialize", {
            "protocolVersion": "2024-11-05",
            "capabilities": {
                "tools": {},
                "resources": {},
                "prompts": {}
            },
            "clientInfo": {"name": "mycode", "version": "0.5.0"}
        })

        # Discover tools
        await self._discover_tools(name)
        # Discover resources
        await self._discover_resources(name)
        # Discover prompts
        await self._discover_prompts(name)

    def _get_transport(self, name: str) -> Optional[MCPTransport]:
        return self.transports.get(name)

    async def _send_request(self, server_name: str, method: str, params: Dict = None, request_id: int = None) -> Optional[Dict]:
        """Send a request and wait for response."""
        transport = self.transports.get(name)
        if not transport:
            return None

        request_id = request_id or int(uuid.uuid4().int & 0xFFFFFFFF)
        message = MCPMessage(
            id=request_id,
            method=method,
            params=params or {}
        )

        # For now, simplified - in production would wait for response
        await transport.send(MCPMessage(
            id=request_id,
            method=method,
            params=params or {}
        ))
        return None

    def _handle_message(self, message: MCPMessage):
        """Handle incoming message from server."""
        # Handle responses, notifications, etc.
        pass

    async def _discover_tools(self, server_name: str):
        """Discover tools from server."""
        # In production, would send tools/list request
        pass

    async def _discover_resources(self, server_name: str):
        """Discover resources from server."""
        pass

    async def _discover_prompts(self, server_name: str):
        """Discover prompts from server."""
        pass

    def get_all_tools(self) -> List[MCPTool]:
        """Get all tools from all connected servers."""
        return list(self.tools.values())

    def get_all_resources(self) -> List[MCPResource]:
        """Get all resources from all connected servers."""
        return list(self.resources.values())

    def get_all_prompts(self) -> List[MCPPrompt]:
        """Get all prompts from all connected servers."""
        return list(self.prompts.values())

    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Any:
        """Call a tool on the appropriate server."""
        tool = self.tools.get(tool_name)
        if not tool:
            raise ValueError(f"Tool not found: {tool_name}")

        transport = self.transports.get(tool.server_name)
        if not transport:
            raise RuntimeError(f"Server not connected: {tool.server_name}")

        # Send tool call
        request_id = int(uuid.uuid4().int & 0xFFFFFFFF)
        await transport.send(MCPMessage(
            id=int(uuid.uuid4().int & 0xFFFFFFFF),
            method="tools/call",
            params={"name": tool_name, "arguments": arguments}
        ))
        # In production, wait for response
        return None

    async def read_resource(self, uri: str) -> Any:
        """Read a resource from the appropriate server."""
        resource = self.resources.get(uri)
        if not resource:
            raise ValueError(f"Resource not found: {uri}")

        transport = self.transports.get(resource.server_name)
        if not transport:
            raise RuntimeError(f"Server not connected: {resource.server_name}")

        return None

    async def get_prompt(self, prompt_name: str, arguments: Dict[str, Any]) -> Any:
        """Get a prompt template from the appropriate server."""
        prompt = self.prompts.get(prompt_name)
        if not prompt:
            raise ValueError(f"Prompt not found: {prompt_name}")

        return None


# Global MCP client instance
_mcp_client: Optional[MCPClient] = None


def get_mcp_client(config_dir: Optional[Path] = None) -> MCPClient:
    """Get or create the global MCP client."""
    global _mcp_client
    if _mcp_client is None:
        _mcp_client = MCPClient(config_dir)
    return _mcp_client


# CLI command functions
def mcp_add(name: str, transport: str, url: str = None, command: str = None, args: List[str] = None) -> bool:
    """Add an MCP server."""
    client = get_mcp_client()
    config = MCPServerConfig(
        name=name,
        transport=transport,
        url=url,
        command=command,
        args=args or []
    )
    return client.add_server(config)


def mcp_remove(name: str) -> bool:
    """Remove an MCP server."""
    client = get_mcp_client()
    return client.remove_server(name)


def mcp_list() -> List[Dict]:
    """List all MCP servers."""
    client = get_mcp_client()
    servers = client.list_servers()
    return [
        {
            "name": s.name,
            "transport": s.transport,
            "url": s.url,
            "command": s.command,
            "enabled": s.enabled
        }
        for s in servers
    ]


async def mcp_connect(name: str) -> bool:
    """Connect to an MCP server."""
    client = get_mcp_client()
    return await client.connect_server(name)


async def mcp_disconnect(name: str) -> bool:
    """Disconnect from an MCP server."""
    client = get_mcp_client()
    return await client.disconnect_server(name)


def mcp_tools() -> List[Dict]:
    """List all available MCP tools."""
    client = get_mcp_client()
    tools = client.get_all_tools()
    return [
        {
            "name": t.name,
            "description": t.description,
            "server": t.server_name,
            "schema": t.input_schema
        }
        for t in tools
    ]


def mcp_resources() -> List[Dict]:
    """List all available MCP resources."""
    client = get_mcp_client()
    resources = client.get_all_resources()
    return [
        {
            "uri": r.uri,
            "name": r.name,
            "description": r.description,
            "server": r.server_name
        }
        for r in resources
    ]


def mcp_prompts() -> List[Dict]:
    """List all available MCP prompts."""
    client = get_mcp_client()
    prompts = client.get_all_prompts()
    return [
        {
            "name": p.name,
            "description": p.description,
            "server": p.server_name
        }
        for p in prompts
    ]