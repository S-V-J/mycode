"""Hook system core for MyCode - Event-driven automation and extensibility."""

from enum import Enum
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Callable, Union
from pathlib import Path
import json
import yaml
import asyncio
from rich.console import Console

console = Console()


class HookEvent(str, Enum):
    """Hook lifecycle events from Anthropic's official documentation."""
    SESSION_START = "SessionStart"
    SETUP = "Setup"
    INSTRUCTIONS_LOADED = "InstructionsLoaded"
    USER_PROMPT_SUBMIT = "UserPromptSubmit"
    USER_PROMPT_EXPANSION = "UserPromptExpansion"
    MESSAGE_DISPLAY = "MessageDisplay"
    PRE_TOOL_USE = "PreToolUse"
    PERMISSION_REQUEST = "PermissionRequest"
    POST_TOOL_USE = "PostToolUse"
    POST_TOOL_USE_FAILURE = "PostToolUseFailure"
    POST_TOOL_BATCH = "PostToolBatch"
    PERMISSION_DENIED = "PermissionDenied"
    NOTIFICATION = "Notification"
    SUBAGENT_START = "SubagentStart"
    SUBAGENT_STOP = "SubagentStop"
    TASK_CREATED = "TaskCreated"
    TASK_COMPLETED = "TaskCompleted"
    STOP = "Stop"
    STOP_FAILURE = "StopFailure"
    TEAMMATE_IDLE = "TeammateIdle"
    CONFIG_CHANGE = "ConfigChange"
    CWD_CHANGED = "CwdChanged"
    DIRECTORY_ADDED = "DirectoryAdded"
    FILE_CHANGED = "FileChanged"
    WORKTREE_CREATE = "WorktreeCreate"
    WORKTREE_REMOVE = "WorktreeRemove"
    PRE_COMPACT = "PreCompact"
    POST_COMPACT = "PostCompact"
    SESSION_END = "SessionEnd"
    ELICITATION = "Elicitation"
    ELICITATION_RESULT = "ElicitationResult"


class HookHandlerType(str, Enum):
    """Hook handler types."""
    COMMAND = "command"
    HTTP = "http"
    MCP_TOOL = "mcp_tool"
    PROMPT_BASED = "prompt_based"
    AGENT_BASED = "agent_based"


@dataclass
class HookConfig:
    """Configuration for a single hook."""
    event: HookEvent
    matcher: Optional[str] = None  # Tool name or pattern to match
    handler: HookHandlerType = HookHandlerType.COMMAND
    command: Optional[str] = None  # For command handler
    url: Optional[str] = None  # For HTTP handler
    payload: Optional[str] = None  # For HTTP handler payload template
    mcp_server: Optional[str] = None  # For MCP tool handler
    mcp_tool: Optional[str] = None  # For MCP tool handler
    prompt: Optional[str] = None  # For prompt-based handler
    agent: Optional[str] = None  # For agent-based handler
    timeout: int = 30  # Timeout in seconds
    enabled: bool = True


@dataclass
class HookContext:
    """Context passed to hook handlers."""
    event: HookEvent
    tool_name: Optional[str] = None
    tool_args: Optional[Dict[str, Any]] = None
    tool_result: Optional[str] = None
    session_id: Optional[str] = None
    user_prompt: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class HookRegistry:
    """Registry for managing hook configurations and execution."""

    def __init__(self, config_path: Optional[Path] = None):
        self.config_path = config_path or Path.home() / ".mycode" / "hooks.json"
        self.hooks: List[HookConfig] = []
        self._load_config()

    def _load_config(self):
        """Load hook configuration from file."""
        if self.config_path.exists():
            try:
                with open(self.config_path, 'r') as f:
                    if self.config_path.suffix in ('.yaml', '.yml'):
                        data = yaml.safe_load(f)
                    else:
                        data = json.load(f)

                if data and 'hooks' in data:
                    for hook_data in data['hooks']:
                        hook = HookConfig(
                            event=HookEvent(hook_data['event']),
                            matcher=hook_data.get('matcher'),
                            handler=HookHandlerType(hook_data.get('handler', 'command')),
                            command=hook_data.get('command'),
                            url=hook_data.get('url'),
                            payload=hook_data.get('payload'),
                            mcp_server=hook_data.get('mcp_server'),
                            mcp_tool=hook_data.get('mcp_tool'),
                            prompt=hook_data.get('prompt'),
                            agent=hook_data.get('agent'),
                            timeout=hook_data.get('timeout', 30),
                            enabled=hook_data.get('enabled', True)
                        )
                        self.hooks.append(hook)
            except Exception as e:
                console.print(f"[yellow]Warning: Failed to load hook config: {e}[/yellow]")

    def save_config(self):
        """Save hook configuration to file."""
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            'hooks': [
                {
                    'event': hook.event.value,
                    'matcher': hook.matcher,
                    'handler': hook.handler.value,
                    'command': hook.command,
                    'url': hook.url,
                    'payload': hook.payload,
                    'mcp_server': hook.mcp_server,
                    'mcp_tool': hook.mcp_tool,
                    'prompt': hook.prompt,
                    'agent': hook.agent,
                    'timeout': hook.timeout,
                    'enabled': hook.enabled
                }
                for hook in self.hooks
            ]
        }
        with open(self.config_path, 'w') as f:
            json.dump(data, f, indent=2)

    def add_hook(self, hook: HookConfig):
        """Add a new hook."""
        self.hooks.append(hook)
        self.save_config()

    def remove_hook(self, index: int):
        """Remove a hook by index."""
        if 0 <= index < len(self.hooks):
            self.hooks.pop(index)
            self.save_config()

    def get_hooks_for_event(self, event: HookEvent, tool_name: Optional[str] = None) -> List[HookConfig]:
        """Get all enabled hooks for a specific event, optionally filtered by tool name."""
        hooks = [h for h in self.hooks if h.event == event and h.enabled]
        if tool_name:
            hooks = [h for h in hooks if not h.matcher or h.matcher == tool_name or h.matcher in tool_name]
        return hooks


class HookExecutor:
    """Executes hooks with appropriate handlers."""

    def __init__(self, registry: HookRegistry):
        self.registry = registry

    async def execute_hooks(self, event: HookEvent, context: HookContext) -> List[Any]:
        """Execute all hooks for an event."""
        hooks = self.registry.get_hooks_for_event(event, context.tool_name)
        results = []

        for hook in self.registry.hooks:
            if hook.event != event or not hook.enabled:
                continue
            if hook.matcher and context.tool_name and hook.matcher != context.tool_name:
                continue

            try:
                result = await self._execute_hook(hook, context)
                results.append({"hook": hook, "result": result, "success": True})
            except Exception as e:
                console.print(f"[red]Hook execution failed: {e}[/red]")
                results.append({"hook": hook, "error": str(e), "success": False})

        return results

    async def _execute_hook(self, hook: HookConfig, context: HookContext) -> Any:
        """Execute a single hook with its handler."""
        if hook.handler == HookHandlerType.COMMAND:
            return await self._execute_command(hook, context)
        elif hook.handler == HookHandlerType.HTTP:
            return await self._execute_http(hook, context)
        elif hook.handler == HookHandlerType.MCP_TOOL:
            return await self._execute_mcp_tool(hook, context)
        elif hook.handler == HookHandlerType.PROMPT_BASED:
            return await self._execute_prompt_based(hook, context)
        elif hook.handler == HookHandlerType.AGENT_BASED:
            return await self._execute_agent_based(hook, context)
        else:
            raise ValueError(f"Unknown handler type: {hook.handler}")

    async def _execute_command(self, hook: HookConfig, context: HookContext) -> str:
        """Execute a shell command."""
        import subprocess
        if not hook.command:
            return "No command specified"

        # Template substitution
        cmd = hook.command
        cmd = cmd.replace("{tool.name}", context.tool_name or "")
        cmd = cmd.replace("{tool.args}", json.dumps(context.tool_args or {}))
        cmd = cmd.replace("{tool.result}", context.tool_result or "")
        cmd = cmd.replace("{event}", context.event.value)
        cmd = cmd.replace("{session.id}", context.session_id or "")

        try:
            result = subprocess.run(
                cmd, shell=True, capture_output=True, text=True, timeout=hook.timeout
            )
            return result.stdout
        except subprocess.TimeoutExpired:
            return f"Command timed out after {hook.timeout}s"
        except Exception as e:
            return f"Command failed: {e}"

    async def _execute_http(self, hook: HookConfig, context: HookContext) -> Any:
        """Execute an HTTP webhook."""
        import httpx
        if not hook.url:
            return "No URL specified"

        # Template substitution for payload
        payload = hook.payload or "{}"
        payload = payload.replace("{tool.name}", context.tool_name or "")
        payload = payload.replace("{tool.args}", json.dumps(context.tool_args or {}))
        payload = payload.replace("{tool.result}", context.tool_result or "")
        payload = payload.replace("{event}", context.event.value)
        payload = payload.replace("{session.id}", context.session_id or "")

        try:
            async with httpx.AsyncClient(timeout=hook.timeout) as client:
                response = await client.post(
                    hook.url,
                    json=json.loads(payload),
                    headers={"Content-Type": "application/json"}
                )
                return response.json()
        except Exception as e:
            return f"HTTP request failed: {e}"

    async def _execute_mcp_tool(self, hook: HookConfig, context: HookContext) -> Any:
        """Execute an MCP tool (placeholder for Phase 3)."""
        return "MCP tool execution not yet implemented (Phase 3)"

    async def _execute_prompt_based(self, hook: HookConfig, context: HookContext) -> Any:
        """Execute a prompt-based hook (LLM evaluates condition)."""
        # This would call the LLM with a structured prompt
        return "Prompt-based hook not yet fully implemented"

    async def _execute_agent_based(self, hook: HookConfig, context: HookContext) -> Any:
        """Execute an agent-based hook (subagent evaluates)."""
        # This would spawn a subagent
        return "Agent-based hook not yet implemented (Phase 4)"


# Global hook registry instance
_hook_registry: Optional[HookRegistry] = None
_hook_executor: Optional[HookExecutor] = None


def get_hook_registry(config_path: Optional[Path] = None) -> HookRegistry:
    """Get or create the global hook registry."""
    global _hook_registry
    if _hook_registry is None:
        _hook_registry = HookRegistry(config_path)
    return _hook_registry


def get_hook_executor() -> HookExecutor:
    """Get or create the global hook executor."""
    global _hook_executor
    if _hook_executor is None:
        _hook_executor = HookExecutor(get_hook_registry())
    return _hook_executor


async def fire_hook(event: HookEvent, context: HookContext) -> List[Any]:
    """Fire a hook event and execute all matching hooks."""
    executor = get_hook_executor()
    return await executor.execute_hooks(event, context)


def fire_hook_sync(event: HookEvent, context: HookContext) -> List[Any]:
    """Synchronous wrapper for firing hooks."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # Can't run async in sync context, create task
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(asyncio.run, fire_hook(event, context))
                return future.result()
        else:
            return loop.run_until_complete(fire_hook(event, context))
    except RuntimeError:
        return asyncio.run(fire_hook(event, context))