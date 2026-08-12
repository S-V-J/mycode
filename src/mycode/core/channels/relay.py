"""Permission prompt relay for channels."""

import asyncio
import json
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Callable, Awaitable
from pathlib import Path
from enum import Enum
from datetime import datetime
import uuid


class PermissionAction(str, Enum):
    """Permission prompt actions."""
    ALLOW = "allow"
    DENY = "deny"
    ALWAYS_ALLOW = "always_allow"
    ALWAYS_DENY = "always_deny"
    MODIFY = "modify"


class PermissionType(str, Enum):
    """Types of permission requests."""
    TOOL_USE = "tool_use"
    FILE_READ = "file_read"
    FILE_WRITE = "file_write"
    SHELL_COMMAND = "shell_command"
    NETWORK_REQUEST = "network_request"
    MCP_TOOL_CALL = "mcp_tool_call"
    PLUGIN_INSTALL = "plugin_install"
    CUSTOM = "custom"


@dataclass
class PermissionPrompt:
    """A permission prompt awaiting user response."""
    id: str
    type: PermissionType
    title: str
    message: str
    details: Dict[str, Any] = field(default_factory=dict)
    options: List[PermissionAction] = field(default_factory=lambda: [
        PermissionAction.ALLOW, PermissionAction.DENY
    ])
    default_action: PermissionAction = PermissionAction.DENY
    timeout: float = 30.0  # seconds
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    responded_at: Optional[str] = None
    response: Optional[PermissionAction] = None
    modified_args: Optional[Dict[str, Any]] = None
    callback: Optional[Callable[[PermissionAction, Optional[Dict]], Awaitable[None]]] = None
    relay_callback: Optional[Callable[[str, PermissionAction, Optional[Dict]], Awaitable[None]]] = None


class PermissionRelay:
    """Relays permission prompts to external channels (chat, webhook, etc.)."""

    def __init__(self, channel_server=None, channel_client=None):
        self.channel_server = channel_server
        self.channel_client = channel_client
        self.pending_prompts: Dict[str, PermissionPrompt] = {}
        self.permanent_allow: Dict[str, bool] = {}  # key -> True
        self.permanent_deny: Dict[str, bool] = {}
        self._response_waiters: Dict[str, asyncio.Future] = {}

    def _get_permission_key(self, prompt: PermissionPrompt) -> str:
        """Generate a key for permanent allow/deny."""
        return f"{prompt.type.value}:{prompt.details.get('tool', '')}:{prompt.details.get('action', '')}"

    async def request_permission(
        self,
        prompt_type: PermissionType,
        title: str,
        message: str,
        details: Dict[str, Any] = None,
        options: List[PermissionAction] = None,
        default_action: PermissionAction = PermissionAction.DENY,
        timeout: float = 30.0,
        relay: bool = True
    ) -> PermissionAction:
        """Request permission from user, optionally relaying to channel."""
        import uuid

        prompt_id = str(uuid.uuid4())[:8]
        key = f"{prompt_type.value}:{details.get('tool', '')}:{details.get('action', '')}"

        # Check permanent allow/deny
        if key in self.permanent_allow:
            return PermissionAction.ALLOW
        if key in self.permanent_deny:
            return PermissionAction.DENY

        prompt = PermissionPrompt(
            id=prompt_id,
            type=prompt_type,
            title=title,
            message=message,
            details=details or {},
            options=options or [PermissionAction.ALLOW, PermissionAction.DENY],
            default_action=default_action,
            timeout=timeout
        )

        self.pending_prompts[prompt_id] = prompt

        # Create future for response
        future = asyncio.get_event_loop().create_future()
        self._response_waiters[prompt_id] = future

        # Relay to channel if available
        if relay and (self.channel_server or self.channel_client):
            await self._relay_prompt(prompt)

        # Wait for response with timeout
        try:
            response = await asyncio.wait_for(future, timeout=timeout)
        except asyncio.TimeoutError:
            response = default_action
            prompt.response = response
            prompt.responded_at = datetime.now().isoformat()

        # Cleanup
        if prompt_id in self.pending_prompts:
            del self.pending_prompts[prompt_id]
        if prompt_id in self._response_waiters:
            del self._response_waiters[prompt_id]

        # Handle permanent actions
        if response == PermissionAction.ALWAYS_ALLOW:
            self.permanent_allow[key] = True
            response = PermissionAction.ALLOW
        elif response == PermissionAction.ALWAYS_DENY:
            self.permanent_deny[key] = True
            response = PermissionAction.DENY

        # Call relay callback if set
        if prompt.relay_callback:
            try:
                await prompt.relay_callback(prompt_id, response, prompt.modified_args)
            except Exception:
                pass

        return response

    async def _relay_prompt(self, prompt: PermissionPrompt):
        """Relay prompt to channel server/client."""
        from .server import ChannelEvent, EventType, ChannelEvent

        event = ChannelEvent.create(
            type=EventType.PERMISSION_REQUEST,
            source="permission_relay",
            payload={
                "prompt_id": prompt.id,
                "type": prompt.type.value,
                "title": prompt.title,
                "message": prompt.message,
                "details": prompt.details,
                "options": [opt.value for opt in prompt.options],
                "default_action": prompt.default_action.value,
                "timeout": prompt.timeout
            }
        )

        if self.channel_server:
            await self.channel_server.emit(event)
        elif self.channel_client:
            await self.channel_client.send_event(event)

    def respond(self, prompt_id: str, action: PermissionAction, modified_args: Dict[str, Any] = None) -> bool:
        """Respond to a pending prompt."""
        if prompt_id not in self.pending_prompts:
            return False

        prompt = self.pending_prompts[prompt_id]
        prompt.response = action
        prompt.modified_args = modified_args
        prompt.responded_at = datetime.now().isoformat()

        # Resolve future
        if prompt_id in self._response_waiters:
            future = self._response_waiters[prompt_id]
            if not future.done():
                future.set_result(action)

        return True

    def get_pending_prompts(self) -> List[PermissionPrompt]:
        """Get all pending prompts."""
        return list(self.pending_prompts.values())

    def cancel_prompt(self, prompt_id: str) -> bool:
        """Cancel a pending prompt."""
        if prompt_id in self.pending_prompts:
            prompt = self.pending_prompts[prompt_id]
            prompt.response = PermissionAction.DENY
            prompt.responded_at = datetime.now().isoformat()

            if prompt_id in self._response_waiters:
                future = self._response_waiters[prompt_id]
                if not future.done():
                    future.set_result(PermissionAction.DENY)

            return True
        return False

    def clear_permanent(self, key: str = None):
        """Clear permanent allow/deny rules."""
        if key:
            self.permanent_allow.pop(key, None)
            self.permanent_deny.pop(key, None)
        else:
            self.permanent_allow.clear()
            self.permanent_deny.clear()


class ChatBridgeRelay:
    """Relays permission prompts to a chat bridge (Discord, Slack, etc.)."""

    def __init__(self, bridge_config: Dict[str, Any]):
        self.config = bridge_config
        self.platform = bridge_config.get("platform", "generic")
        self.webhook_url = bridge_config.get("webhook_url")
        self.channel_id = bridge_config.get("channel_id")
        self.bot_token = bridge_config.get("bot_token")

    async def send_prompt(self, prompt: PermissionPrompt) -> str:
        """Send prompt to chat bridge and return message ID."""
        import httpx

        # Format prompt for chat
        message = self._format_prompt(prompt)

        if self.platform == "discord":
            return await self._send_discord(message)
        elif self.platform == "slack":
            return await self._send_slack(message)
        elif self.platform == "telegram":
            return await self._send_telegram(message)
        else:
            return await self._send_generic(message)

    def _format_prompt(self, prompt: PermissionPrompt) -> Dict[str, Any]:
        """Format prompt for chat platform."""
        options_text = "\n".join([f"• {opt.value}" for opt in prompt.options])

        return {
            "title": prompt.title,
            "message": prompt.message,
            "options": [opt.value for opt in prompt.options],
            "default": prompt.default_action.value,
            "details": prompt.details,
            "prompt_id": prompt.id
        }

    async def _send_discord(self, message: Dict[str, Any]) -> str:
        """Send to Discord via webhook."""
        import httpx

        embed = {
            "title": message["title"],
            "description": message["message"],
            "color": 0xFFAA00,
            "fields": [
                {"name": "Options", "value": "\n".join([f"• {opt}" for opt in message["options"]]), "inline": False},
                {"name": "Default", "value": message["default"], "inline": True},
            ],
            "footer": {"text": f"Prompt ID: {message['prompt_id']}"}
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.webhook_url,
                json={"embeds": [embed]}
            )
            response.raise_for_status()
            return response.headers.get("X-Message-ID", "unknown")

    async def _send_slack(self, message: Dict[str, Any]) -> str:
        """Send to Slack via webhook."""
        import httpx

        blocks = [
            {"type": "header", "text": {"type": "plain_text", "text": message["title"]}},
            {"type": "section", "text": {"type": "mrkdwn", "text": message["message"]}},
            {"type": "divider"},
            {"type": "section", "text": {"type": "mrkdwn", "text": f"*Options:*\n" + "\n".join([f"• `{opt}`" for opt in message["options"]])}},
            {"type": "context", "elements": [{"type": "mrkdwn", "text": f"Default: {message['default']} | Prompt ID: {message['prompt_id']}"}]}
        ]

        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.webhook_url,
                json={"blocks": blocks}
            )
            response.raise_for_status()
            return "slack_message"

    async def _send_telegram(self, message: Dict[str, Any]) -> str:
        """Send to Telegram via bot API."""
        import httpx

        text = f"*{message['title']}*\n\n{message['message']}\n\n*Options:*\n" + "\n".join([f"• `{opt}`" for opt in message["options"]])
        text += f"\n\n*Default:* {message['default']}"

        keyboard = {
            "inline_keyboard": [[{"text": opt, "callback_data": f"perm_{message['prompt_id']}_{opt}"}] for opt in message["options"]]
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"https://api.telegram.org/bot{self.bot_token}/sendMessage",
                json={
                    "chat_id": self.channel_id,
                    "text": text,
                    "parse_mode": "Markdown",
                    "reply_markup": keyboard
                }
            )
            response.raise_for_status()
            return str(response.json()["result"]["message_id"])

    async def _send_generic(self, message: Dict[str, Any]) -> str:
        """Send to generic webhook."""
        import httpx

        async with httpx.AsyncClient() as client:
            response = await client.post(self.webhook_url, json=message)
            response.raise_for_status()
            return "generic"

    async def handle_response(self, platform: str, data: Dict[str, Any]) -> tuple:
        """Handle response from chat bridge. Returns (prompt_id, action)."""
        if platform == "discord":
            # Discord interaction
            prompt_id = data.get("data", {}).get("custom_id", "").replace("perm_", "")
            action_str = data.get("data", {}).get("values", [""])[0]
        elif platform == "slack":
            # Slack block action
            prompt_id = data.get("actions", [{}])[0].get("value", "").replace("perm_", "")
            action_str = data.get("actions", [{}])[0].get("selected_option", {}).get("value", "")
        elif platform == "telegram":
            # Telegram callback query
            callback_data = data.get("callback_query", {}).get("data", "")
            parts = callback_data.split("_")
            prompt_id = parts[1] if len(parts) > 1 else ""
            action_str = parts[2] if len(parts) > 2 else ""
        else:
            prompt_id = data.get("prompt_id", "")
            action_str = data.get("action", "")

        try:
            action = PermissionAction(action_str)
        except ValueError:
            action = PermissionAction.DENY

        return prompt_id, action


class TerminalPermissionUI:
    """Terminal-based permission UI (for local use)."""

    def __init__(self, console=None):
        from rich.console import Console
        self.console = console or Console()

    async def prompt(self, prompt: PermissionPrompt) -> tuple:
        """Show prompt in terminal and get response."""
        from rich.panel import Panel
        from rich.prompt import Prompt
        from rich.table import Table

        # Display prompt
        self.console.print(Panel(
            f"[bold]{prompt.title}[/bold]\n\n{prompt.message}",
            title="Permission Request",
            border_style="yellow"
        ))

        # Show details
        if prompt.details:
            table = Table(title="Details")
            table.add_column("Key", style="cyan")
            table.add_column("Value", style="white")
            for k, v in prompt.details.items():
                table.add_row(k, str(v))
            self.console.print(table)

        # Show options
        options_str = "/".join([opt.value for opt in prompt.options])
        default = prompt.default_action.value

        response = Prompt.ask(
            f"[bold]Action[/bold] ({options_str})",
            choices=[opt.value for opt in prompt.options],
            default=default
        )

        action = PermissionAction(response)
        modified_args = None

        # If modify action, ask for modifications
        if action == PermissionAction.MODIFY:
            self.console.print("[dim]Enter modified arguments as JSON (empty to keep original):[/dim]")
            try:
                import json
                modified_input = Prompt.ask("Modified args", default="{}")
                modified_args = json.loads(modified_input)
            except Exception:
                pass

        return action, modified_args