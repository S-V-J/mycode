"""Channels system for MyCode - webhooks, relays, and event handling."""

from .server import (
    ChannelServer,
    ChannelClient,
    ChannelEvent,
    EventType,
    ChannelType,
    WebhookConfig,
)

from .relay import (
    PermissionRelay,
    ChatBridgeRelay,
    TerminalPermissionUI,
    PermissionPrompt,
    PermissionAction,
    PermissionType,
)

# Global instances
_channel_server = None
_permission_relay = None


def get_channel_server(host: str = "localhost", port: int = 8765) -> ChannelServer:
    """Get or create the global channel server."""
    global _channel_server
    if _channel_server is None:
        _channel_server = ChannelServer(host, port)
    return _channel_server


def get_permission_relay(channel_server=None, channel_client=None) -> PermissionRelay:
    """Get or create the global permission relay."""
    global _permission_relay
    if _permission_relay is None:
        _permission_relay = PermissionRelay(channel_server, channel_client)
    return _permission_relay


__all__ = [
    # Server
    "ChannelServer",
    "ChannelClient",
    "ChannelEvent",
    "EventType",
    "ChannelType",
    "WebhookConfig",
    # Relay
    "PermissionRelay",
    "ChatBridgeRelay",
    "TerminalPermissionUI",
    "PermissionPrompt",
    "PermissionAction",
    "PermissionType",
    # Helpers
    "get_channel_server",
    "get_permission_relay",
]