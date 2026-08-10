"""AI Operational Modes for MyCode Agent."""

from enum import Enum
from dataclasses import dataclass
from typing import Optional, List, Dict, Any
from rich.console import Console

console = Console()


class AgentMode(Enum):
    """AI Operational Modes."""
    AUTO = "⏵⏵ AUTO"
    PLAN = "⏸ PLAN"
    MANUAL = "⏸ MANUAL"
    AEROPLANE = "✈️ AEROPLANE"

    @property
    def description(self) -> str:
        descriptions = {
            AgentMode.AUTO: "Full autonomous execution. Safe tools run instantly; destructive tools prompt for approval.",
            AgentMode.PLAN: "AI generates multi-step plan and tool calls, but pauses execution. User reviews and approves.",
            AgentMode.MANUAL: "AI acts as pair-programmer. Suggests code/commands in chat. Tools are disabled.",
            AgentMode.AEROPLANE: "Offline/Read-only. No external API calls. Relies strictly on local cache and RAG.",
        }
        return descriptions[self]

    @property
    def allows_tools(self) -> bool:
        return self != AgentMode.MANUAL

    @property
    def allows_external_api(self) -> bool:
        return self != AgentMode.AEROPLANE

    @property
    def requires_approval(self) -> bool:
        return self == AgentMode.PLAN

    @property
    def auto_execute_safe(self) -> bool:
        return self == AgentMode.AUTO


@dataclass
class ToolCallPlan:
    """Represents a planned tool call for approval."""
    name: str
    args: Dict[str, Any]
    description: str
    is_destructive: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "args": self.args,
            "description": self.description,
            "is_destructive": self.is_destructive,
        }


@dataclass
class ExecutionPlan:
    """Represents a multi-step execution plan for Plan Mode."""
    steps: List[ToolCallPlan]
    summary: str
    estimated_duration: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "steps": [step.to_dict() for step in self.steps],
            "summary": self.summary,
            "estimated_duration": self.estimated_duration,
        }


# Destructive tool patterns that require extra approval even in AUTO mode
DESTRUCTIVE_TOOLS = {"bash", "write_file", "edit_file"}
DESTRUCTIVE_BASH_PATTERNS = [
    "rm -rf", "rm -r", "sudo", "chmod 777", "mkfs", "dd if=",
    ":(){:|:&};:", ">/dev/sda", "shutdown", "reboot", "kill -9",
    "chown -R", "chmod -R", "mv /", "cp /dev/null"
]


def is_destructive_bash(command: str) -> bool:
    """Check if a bash command is potentially destructive."""
    command_lower = command.lower().strip()
    return any(pattern in command_lower for pattern in DESTRUCTIVE_BASH_PATTERNS)


def is_destructive_tool(name: str, args: Dict[str, Any]) -> bool:
    """Check if a tool call is potentially destructive."""
    if name in DESTRUCTIVE_TOOLS:
        if name == "bash":
            return is_destructive_bash(args.get("command", ""))
        return True  # write_file and edit_file are always potentially destructive
    return False


def get_mode_from_string(mode_str: str) -> AgentMode:
    """Parse mode string to AgentMode enum."""
    for mode in AgentMode:
        if mode.value == mode_str:
            return mode
    return AgentMode.AUTO


def cycle_mode(current: AgentMode) -> AgentMode:
    """Cycle to the next mode."""
    modes = list(AgentMode)
    current_idx = modes.index(current)
    return modes[(current_idx + 1) % len(modes)]