"""Core module exports for MyCode."""

from .config import ensure_config, find_mycode_md
from .llm_client import NemotronClient
from .agent import Agent
from .cache import (
    check_cache,
    save_to_cache,
    invalidate_cache_for_file,
    create_session,
    get_sessions,
    get_session,
    update_session_name,
    delete_session,
    add_message,
    get_messages,
    get_or_create_default_session
)
from .rag import index_directory, start_watcher, retrieve_context, index_file
from .modes import (
    AgentMode,
    ToolCallPlan,
    ExecutionPlan,
    is_destructive_tool,
    is_destructive_bash,
    get_mode_from_string,
    cycle_mode
)

__all__ = [
    "ensure_config",
    "find_mycode_md",
    "NemotronClient",
    "Agent",
    "check_cache",
    "save_to_cache",
    "invalidate_cache_for_file",
    "create_session",
    "get_sessions",
    "get_session",
    "update_session_name",
    "delete_session",
    "add_message",
    "get_messages",
    "get_or_create_default_session",
    "index_directory",
    "start_watcher",
    "retrieve_context",
    "index_file",
    "AgentMode",
    "ToolCallPlan",
    "ExecutionPlan",
    "is_destructive_tool",
    "is_destructive_bash",
    "get_mode_from_string",
    "cycle_mode",
]