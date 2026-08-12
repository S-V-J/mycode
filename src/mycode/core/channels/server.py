"""Channel server for webhook reception and event handling."""

import json
import asyncio
import hmac
import hashlib
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Callable, Awaitable
from pathlib import Path
from enum import Enum
from datetime import datetime
from aiohttp import web
import httpx


class ChannelType(str, Enum):
    """Types of channels."""
    WEBHOOK = "webhook"
    SSE = "sse"
    WEBSOCKET = "websocket"


class EventType(str, Enum):
    """Standard event types."""
    TOOL_USE = "tool.use"
    TOOL_RESULT = "tool.result"
    PROMPT = "prompt"
    PERMISSION_REQUEST = "permission.request"
    PERMISSION_RESPONSE = "permission.response"
    ERROR = "error"
    INFO = "info"
    CUSTOM = "custom"


@dataclass
class ChannelEvent:
    """Standardized event format for channels."""
    id: str
    type: EventType
    source: str
    timestamp: str
    payload: Dict[str, Any]
    metadata: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def create(cls, type: EventType, source: str, payload: Dict[str, Any], metadata: Dict[str, Any] = None) -> "ChannelEvent":
        import uuid
        return cls(
            id=str(uuid.uuid4()),
            type=type,
            source=source,
            timestamp=datetime.now().isoformat(),
            payload=payload,
            metadata=metadata or {}
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "type": self.type.value,
            "source": self.source,
            "timestamp": self.timestamp,
            "payload": self.payload,
            "metadata": self.metadata
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ChannelEvent":
        return cls(
            id=data["id"],
            type=EventType(data["type"]),
            source=data["source"],
            timestamp=data["timestamp"],
            payload=data["payload"],
            metadata=data.get("metadata", {})
        )


@dataclass
class WebhookConfig:
    """Webhook endpoint configuration."""
    path: str
    secret: Optional[str] = None
    allowed_ips: List[str] = field(default_factory=list)
    headers: Dict[str, str] = field(default_factory=dict)
    verify_signature: bool = True


class ChannelServer:
    """HTTP server for receiving webhooks and serving events."""

    def __init__(self, host: str = "localhost", port: int = 8765):
        self.host = host
        self.port = port
        self.app = web.Application()
        self.webhooks: Dict[str, WebhookConfig] = {}
        self.event_handlers: Dict[EventType, List[Callable[[ChannelEvent], Awaitable[None]]]] = {}
        self.global_handlers: List[Callable[[ChannelEvent], Awaitable[None]]] = []
        self.runner: Optional[web.AppRunner] = None
        self.site: Optional[web.TCPSite] = None
        self._setup_routes()

    def _setup_routes(self):
        """Setup HTTP routes."""
        self.app.router.add_post("/webhook/{webhook_id}", self._handle_webhook)
        self.app.router.add_get("/events", self._handle_events_sse)
        self.app.router.add_get("/ws", self._handle_websocket)
        self.app.router.add_get("/health", self._handle_health)
        self.app.router.add_post("/events", self._handle_event_post)

    def register_webhook(self, webhook_id: str, config: WebhookConfig):
        """Register a webhook endpoint."""
        self.webhooks[webhook_id] = config

    def unregister_webhook(self, webhook_id: str) -> bool:
        """Unregister a webhook endpoint."""
        if webhook_id in self.webhooks:
            del self.webhooks[webhook_id]
            return True
        return False

    def on_event(self, event_type: EventType, handler: Callable[[ChannelEvent], Awaitable[None]]):
        """Register an event handler for a specific event type."""
        if event_type not in self.event_handlers:
            self.event_handlers[event_type] = []
        self.event_handlers[event_type].append(handler)

    def on_any_event(self, handler: Callable[[ChannelEvent], Awaitable[None]]):
        """Register a global event handler."""
        self.global_handlers.append(handler)

    async def _handle_webhook(self, request: web.Request) -> web.Response:
        """Handle incoming webhook."""
        webhook_id = request.match_info["webhook_id"]
        config = self.webhooks.get(webhook_id)

        if not config:
            return web.Response(status=404, text="Webhook not found")

        # Verify IP
        if config.allowed_ips:
            client_ip = request.remote
            if client_ip not in config.allowed_ips:
                return web.Response(status=403, text="IP not allowed")

        # Verify signature
        if config.verify_signature and config.secret:
            signature = request.headers.get("X-Signature") or request.headers.get("X-Hub-Signature-256")
            if not signature:
                return web.Response(status=401, text="Missing signature")

            body = await request.read()
            expected = hmac.new(
                config.secret.encode(),
                body,
                hashlib.sha256
            ).hexdigest()

            if not hmac.compare_digest(signature.replace("sha256=", ""), expected):
                return web.Response(status=401, text="Invalid signature")

        # Parse payload
        try:
            payload = await request.json()
        except Exception:
            payload = {"raw": await request.text()}

        # Create event
        event = ChannelEvent.create(
            type=EventType.CUSTOM,
            source=f"webhook:{webhook_id}",
            payload=payload,
            metadata={"headers": dict(request.headers)}
        )

        # Dispatch event
        await self._dispatch_event(event)

        return web.Response(status=200, text="OK")

    async def _handle_event_post(self, request: web.Request) -> web.Response:
        """Handle direct event POST."""
        try:
            data = await request.json()
            event = ChannelEvent.from_dict(data)
        except Exception:
            return web.Response(status=400, text="Invalid event format")

        await self._dispatch_event(event)
        return web.Response(status=200, text="OK")

    async def _handle_events_sse(self, request: web.Request) -> web.Response:
        """Handle Server-Sent Events connection."""
        response = web.StreamResponse(
            status=200,
            headers={
                "Content-Type": "text/event-stream",
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
            }
        )
        await response.prepare(request)

        # Send initial comment to keep connection alive
        await response.write(b": connected\n\n")

        # Register this connection
        queue = asyncio.Queue()
        handler_id = id(queue)

        async def sse_handler(event: ChannelEvent):
            await queue.put(event)

        self.global_handlers.append(sse_handler)

        try:
            async for event in self._event_generator(queue):
                data = json.dumps(event.to_dict())
                await response.write(f"data: {data}\n\n".encode())
        except asyncio.CancelledError:
            pass
        finally:
            self.global_handlers.remove(sse_handler)

        return response

    async def _event_generator(self, queue: asyncio.Queue):
        """Generate events from queue."""
        while True:
            try:
                event = await asyncio.wait_for(queue.get(), timeout=30.0)
                yield event
            except asyncio.TimeoutError:
                yield ChannelEvent.create(EventType.INFO, "server", {"ping": True})
            except Exception:
                break

    async def _handle_websocket(self, request: web.Request) -> web.Response:
        """Handle WebSocket connection."""
        ws = web.WebSocketResponse()
        await ws.prepare(request)

        queue = asyncio.Queue()

        async def ws_handler(event: ChannelEvent):
            await queue.put(event)

        self.global_handlers.append(ws_handler)

        try:
            # Sender task
            async def sender():
                async for event in self._event_generator(queue):
                    await ws.send_json(event.to_dict())

            sender_task = asyncio.create_task(sender())

            # Receiver loop
            async for msg in ws:
                if msg.type == web.WSMsgType.TEXT:
                    try:
                        data = json.loads(msg.data)
                        event = ChannelEvent.from_dict(data)
                        await self._dispatch_event(event)
                    except Exception:
                        pass
                elif msg.type == web.WSMsgType.ERROR:
                    break

            sender_task.cancel()
        finally:
            self.global_handlers.remove(ws_handler)

        return ws

    async def _handle_health(self, request: web.Request) -> web.Response:
        """Health check endpoint."""
        return web.json_response({
            "status": "healthy",
            "webhooks": list(self.webhooks.keys()),
            "handlers": {et.value: len(h) for et, h in self.event_handlers.items()}
        })

    async def _dispatch_event(self, event: ChannelEvent):
        """Dispatch event to handlers."""
        # Global handlers
        for handler in self.global_handlers:
            try:
                await handler(event)
            except Exception:
                pass

        # Type-specific handlers
        handlers = self.event_handlers.get(event.type, [])
        for handler in handlers:
            try:
                await handler(event)
            except Exception:
                pass

    async def emit(self, event: ChannelEvent):
        """Emit an event to all connected clients."""
        await self._dispatch_event(event)

    async def emit_event(self, type: EventType, source: str, payload: Dict[str, Any], metadata: Dict[str, Any] = None):
        """Convenience method to create and emit an event."""
        event = ChannelEvent.create(type, source, payload, metadata)
        await self.emit(event)

    async def start(self):
        """Start the server."""
        self.runner = web.AppRunner(self.app)
        await self.runner.setup()
        self.site = web.TCPSite(self.runner, self.host, self.port)
        await self.site.start()

    async def stop(self):
        """Stop the server."""
        if self.site:
            await self.site.stop()
        if self.runner:
            await self.runner.cleanup()


class ChannelClient:
    """Client for sending events to a channel server."""

    def __init__(self, base_url: str, auth_token: str = None):
        self.base_url = base_url.rstrip("/")
        self.auth_token = auth_token
        self.client: Optional[httpx.AsyncClient] = None

    async def connect(self):
        """Connect to the channel server."""
        headers = {}
        if self.auth_token:
            headers["Authorization"] = f"Bearer {self.auth_token}"
        self.client = httpx.AsyncClient(base_url=self.base_url, headers=headers, timeout=30.0)

    async def disconnect(self):
        """Disconnect from the channel server."""
        if self.client:
            await self.client.aclose()
            self.client = None

    async def send_event(self, event: ChannelEvent) -> bool:
        """Send an event to the server."""
        if not self.client:
            await self.connect()

        try:
            response = await self.client.post("/events", json=event.to_dict())
            return response.status_code == 200
        except Exception:
            return False

    async def send_webhook(self, webhook_id: str, payload: Dict[str, Any]) -> bool:
        """Send a webhook payload."""
        if not self.client:
            await self.connect()

        try:
            response = await self.client.post(f"/webhook/{webhook_id}", json=payload)
            return response.status_code == 200
        except Exception:
            return False

    async def subscribe_sse(self, callback: Callable[[ChannelEvent], Awaitable[None]]):
        """Subscribe to events via SSE."""
        if not self.client:
            await self.connect()

        async with self.client.stream("GET", "/events") as response:
            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    try:
                        data = json.loads(line[6:])
                        event = ChannelEvent.from_dict(data)
                        await callback(event)
                    except Exception:
                        pass

    async def connect_websocket(self, callback: Callable[[ChannelEvent], Awaitable[None]]):
        """Connect via WebSocket."""
        import websockets
        ws_url = self.base_url.replace("http", "ws") + "/ws"
        headers = {}
        if self.auth_token:
            headers["Authorization"] = f"Bearer {self.auth_token}"

        async with websockets.connect(ws_url, extra_headers=headers) as ws:
            async for message in ws:
                try:
                    data = json.loads(message)
                    event = ChannelEvent.from_dict(data)
                    await callback(event)
                except Exception:
                    pass