# Phase 2: Hook System & Automation 🔄 **NEXT**

**Goal:** Event-driven automation and extensibility

## Target Features (36 atomic items from 217 total)

### Hook Lifecycle Events (31)
*From Anthropic's official documentation - each event is a discrete atomic item*

| # | Hook Event | Description | MyCode Implementation Plan |
|---|------------|-------------|---------------------------|
| 1 | SessionStart | Session initialization | `on_session_start()` in agent |
| 2 | Setup | Environment setup | `on_setup()` for config validation |
| 3 | InstructionsLoaded | CLAUDE.md/MYCODE.md loaded | `on_instructions_loaded()` |
| 4 | UserPromptSubmit | User submits prompt | `on_user_prompt_submit()` - pre-processing |
| 5 | UserPromptExpansion | Prompt expansion/rewrite | `on_prompt_expansion()` - template expansion |
| 6 | MessageDisplay | Message rendering | `on_message_display()` - custom formatting |
| 7 | PreToolUse | Before tool execution | `on_pre_tool_use()` - validation, logging |
| 8 | PermissionRequest | Permission prompt | `on_permission_request()` - auto-approve logic |
| 9 | PostToolUse | After successful tool use | `on_post_tool_use()` - logging, metrics |
| 10 | PostToolUseFailure | Tool execution failed | `on_post_tool_failure()` - error handling |
| 11 | PostToolBatch | Batch of tools completed | `on_post_tool_batch()` - batch metrics |
| 12 | PermissionDenied | Permission denied | `on_permission_denied()` - fallback logic |
| 13 | Notification | System notification | `on_notification()` - UI/toast |
| 14 | SubagentStart | Subagent spawned | `on_subagent_start()` - tracking |
| 15 | SubagentStop | Subagent completed | `on_subagent_stop()` - cleanup |
| 16 | TaskCreated | Background task created | `on_task_created()` - task queue |
| 17 | TaskCompleted | Background task done | `on_task_completed()` - result handling |
| 18 | Stop | Session stop requested | `on_stop()` - graceful shutdown |
| 19 | StopFailure | Stop failed | `on_stop_failure()` - force cleanup |
| 20 | TeammateIdle | Teammate waiting | `on_teammate_idle()` - load balancing |
| 21 | ConfigChange | Config modified | `on_config_change()` - hot reload |
| 22 | CwdChanged | Working directory changed | `on_cwd_changed()` - re-index |
| 23 | DirectoryAdded | New directory watched | `on_directory_added()` - index |
| 24 | FileChanged | File modified | `on_file_changed()` - re-index + cache invalidation |
| 25 | WorktreeCreate | Git worktree created | `on_worktree_create()` - isolate |
| 26 | WorktreeRemove | Git worktree removed | `on_worktree_remove()` - cleanup |
| 27 | PreCompact | Before context compaction | `on_pre_compact()` - save state |
| 28 | PostCompact | After context compaction | `on_post_compact()` - restore |
| 29 | SessionEnd | Session ending | `on_session_end()` - persist state |
| 30 | Elicitation | Elicitation request | `on_elicitation()` - user input |
| 31 | ElicitationResult | Elicitation response | `on_elicitation_result()` - process |

### Hook Handler Types (5)
| # | Handler Type | Description | MyCode Implementation |
|---|--------------|-------------|----------------------|
| 1 | Command (shell) | Execute shell command | `subprocess.run()` with timeout |
| 2 | HTTP | POST to webhook URL | `httpx.post()` with JSON payload |
| 3 | MCP tool | Call MCP server tool | Via MCP client (Phase 3) |
| 4 | Prompt-based | LLM evaluates condition | LLM call with structured prompt |
| 5 | Agent-based | Subagent evaluates | Spawn subagent (Phase 4) |

### Scheduled Tasks & Automation (3)
| # | Feature | Description | MyCode Implementation |
|---|---------|-------------|----------------------|
| 1 | `/loop` command | Run prompt repeatedly with interval | `ScheduleWakeup` + cron-style |
| 2 | Cron expressions | Schedule at specific times | `CronCreate`, `CronDelete`, `CronList` |
| 3 | Reminders | One-time scheduled prompts | `ScheduleWakeup` with one-shot |

### Goal Tracking & Non-Interactive (2)
| # | Feature | Description | MyCode Implementation |
|---|---------|-------------|----------------------|
| 1 | `/goal` command | Set session goal with condition | `TaskCreate` with goal tracking |
| 2 | Headless mode | CI/CD, JSON output, streaming | `--headless` flag + JSON output mode |

### Checkpointing & Deep Links (2)
| # | Feature | Description | MyCode Implementation |
|---|---------|-------------|----------------------|
| 1 | Checkpointing | Rewind, summarize, auto-track | Session state snapshots + `/rewind` |
| 2 | Deep links | Session URLs (cwd/repo) | `mycode://session/{id}` protocol |

---

## Implementation Plan

### File Structure
```
src/mycode/core/
├── hooks.py              # Hook system core
├── hooks/
│   ├── __init__.py
│   ├── registry.py       # Hook registration & matching
│   ├── handlers.py       # 5 handler types
│   ├── events.py         # 31 event definitions
│   └── config.py         # Hook configuration (JSON/YAML)
├── scheduler.py          # Cron, loop, reminders
├── checkpoints.py        # Session snapshots, rewind
└── headless.py           # CI/CD mode, JSON output
```

### Hook Configuration (`.mycode/hooks.json`)
```json
{
  "hooks": [
    {
      "event": "PreToolUse",
      "matcher": "bash",
      "handler": "command",
      "command": "echo 'Executing: {tool.name}'"
    },
    {
      "event": "PostToolUse",
      "matcher": "write_file",
      "handler": "http",
      "url": "http://localhost:8080/webhook",
      "payload": "{tool.args}"
    }
  ]
}
```

### Dependencies
- `pyyaml` for hook config
- `croniter` for cron expressions
- `websockets` for MCP tool handler (Phase 3)

---

## Verification Checklist
- [ ] Hook events fire at correct points in agent loop
- [ ] 5 handler types execute correctly
- [ ] Matcher patterns filter correctly (tool name, args)
- [ ] Hook config loads from `.mycode/hooks.json`
- [ ] `/loop` command runs with interval
- [ ] Cron jobs execute on schedule
- [ ] `/goal` tracks and evaluates condition
- [ ] Headless mode outputs JSON
- [ ] Checkpoints save/restore session state
- [ ] Deep links open sessions