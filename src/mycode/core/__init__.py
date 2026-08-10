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
from .hooks import (
    HookRegistry,
    HookExecutor,
    HookEvent,
    HookHandlerType,
    HookConfig,
    HookContext,
    get_hook_registry,
    get_hook_executor,
    fire_hook,
    fire_hook_sync
)
from .scheduler import (
    Scheduler,
    ScheduledJob,
    get_scheduler,
    cron_create,
    cron_delete,
    cron_list,
    loop_create,
    reminder_create
)
from .checkpoints import (
    CheckpointManager,
    DeepLinkManager,
    Checkpoint,
    get_checkpoint_manager,
    get_deep_link_manager,
    checkpoint_create,
    checkpoint_list,
    checkpoint_restore,
    checkpoint_delete,
    deeplink_create,
    deeplink_resolve,
    deeplink_list
)
from .headless import (
    HeadlessRunner,
    HeadlessConfig,
    HeadlessResponse,
    run_headless_sync,
    run_headless
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
    "HookRegistry",
    "HookExecutor",
    "HookEvent",
    "HookHandlerType",
    "HookConfig",
    "HookContext",
    "get_hook_registry",
    "get_hook_executor",
    "fire_hook",
    "fire_hook_sync",
    "Scheduler",
    "ScheduledJob",
    "get_scheduler",
    "cron_create",
    "cron_delete",
    "cron_list",
    "loop_create",
    "reminder_create",
    "CheckpointManager",
    "DeepLinkManager",
    "Checkpoint",
    "get_checkpoint_manager",
    "get_deep_link_manager",
    "checkpoint_create",
    "checkpoint_list",
    "checkpoint_restore",
    "checkpoint_delete",
    "deeplink_create",
    "deeplink_resolve",
    "deeplink_list",
    "HeadlessRunner",
    "HeadlessConfig",
    "HeadlessResponse",
    "run_headless_sync",
    "run_headless",
]