# Phase 3: MCP & Plugin Ecosystem 📋 **PLANNED**

**Goal:** Model Context Protocol and extensible plugin system

## Target Features (46 atomic items from 217 total)

### MCP Transport Types (4)
| # | Transport | Description | MyCode Implementation |
|---|-----------|-------------|----------------------|
| 1 | Remote HTTP | REST API over HTTP/HTTPS | `httpx.AsyncClient` + OpenAPI spec |
| 2 | Remote SSE | Server-Sent Events | `httpx` SSE streaming |
| 3 | Local stdio | Subprocess with stdin/stdout | `subprocess.Popen` with pipes |
| 4 | Remote WebSocket | Full-duplex WebSocket | `websockets` library |

### MCP Installation Scopes (3)
| # | Scope | Description | MyCode Implementation |
|---|-------|-------------|----------------------|
| 1 | Local | Project-specific (`./.mcp.json`) | `.mcp.json` in project root |
| 2 | Project | Shared across team | `.mycode/mcp/` directory |
| 3 | User | Global (`~/.mycode/mcp/`) | `~/.mycode/mcp/` vault |

### MCP Server Management (8)
| # | Feature | Description |
|---|---------|-------------|
| 1 | Add server | `mcp add <name> <url/command>` |
| 2 | Remove server | `mcp remove <name>` |
| 3 | List servers | `mcp list` |
| 3 | Verify server | Health check + tool discovery |
| 4 | Server auth | OAuth, API keys, bearer tokens |
| 5 | Tool discovery | List available tools from server |
| 6 | Resource access | Read MCP resources (files, data) |
| 7 | Prompt templates | Use MCP prompts as commands |
| 8 | Dynamic updates | Auto-reconnect, tool list refresh |

### Plugin System (12)
| # | Feature | Description |
|---|---------|-------------|
| 1 | Plugin manifest | `plugin.json` with metadata, dependencies |
| 2 | Marketplace protocol | Add/remove marketplaces (GitHub, local, npm) |
| 3 | Installation | `plugin install <name>` with deps |
| 4 | Version resolution | Semver constraints, lock file |
| 5 | Enable/disable | Toggle plugins per project/user |
| 6 | Skill integration | Plugins can provide skills |
| 7 | LSP servers | Language servers via plugin |
| 8 | Background monitors | File watchers, log tailers |
| 9 | Themes | Custom TUI color schemes |
| 10 | Hook integration | Plugins register hooks |
| 11 | MCP servers | Plugins can provide MCP servers |
| 12 | Settings schema | Plugin-specific config validation |

### Skills (7)
| # | Feature | Description |
|---|---------|-------------|
| 1 | Skill manifest | `skill.md` with frontmatter |
| 2 | Command registration | `/skill-name` slash command |
| 3 | Argument parsing | Typed arguments with validation |
| 4 | Subagent integration | Skills can spawn subagents |
| 5 | Eval framework | `skill-creator` for testing |
| 6 | Sharing | Export/import skill bundles |
| 7 | Marketplace | Skill discovery and install |

### Artifacts (3)
| # | Feature | Description |
|---|---------|-------------|
| 1 | Visual outputs | HTML/React components in TUI |
| 2 | Live data | MCP connector calls in artifacts |
| 3 | Interactive controls | Forms, sliders, toggles in artifacts |

### Channels (3)
| # | Feature | Description |
|---|---------|-------------|
| 1 | Webhook receiver | HTTP endpoint for external messages |
| 2 | Relay permission prompts | Forward prompts to chat bridge |
| 3 | Notification format | Standardized event schema |

---

## Implementation Plan

### File Structure
```
src/mycode/core/
├── mcp/
│   ├── __init__.py
│   ├── client.py           # MCP client (all 4 transports)
│   ├── server.py           # MCP server management
│   ├── registry.py         # Server registry + tool discovery
│   └── auth.py             # OAuth, API key handling
├── plugins/
│   ├── __init__.py
│   ├── manager.py          # Plugin lifecycle
│   ├── marketplace.py      # Marketplace protocol
│   ├── manifest.py         # Plugin/skill validation
│   └── loader.py           # Dynamic import + sandbox
├── skills/
│   ├── __init__.py
│   ├── registry.py         # Skill registry
│   ├── executor.py         # Skill execution
│   └── eval.py             # Evaluation framework
├── artifacts/
│   ├── __init__.py
│   ├── renderer.py         # TUI artifact rendering
│   └── connector.py        # MCP calls in artifacts
└── channels/
    ├── __init__.py
    ├── server.py           # Webhook server
    └── relay.py            # Permission prompt relay
```

### Configuration Files
- `.mcp.json` - Project MCP servers
- `~/.mycode/mcp/` - User MCP servers
- `.mycode/plugins/` - Installed plugins
- `~/.mycode/plugins/` - User plugins
- `.mycode/skills/` - Project skills
- `~/.mycode/skills/` - User skills

### Dependencies
- `mcp` (official SDK) or custom implementation
- `websockets` for WebSocket transport
- `httpx` for HTTP/SSE
- `pydantic` for manifest validation
- `importlib` for dynamic plugin loading

---

## Verification Checklist
- [ ] All 4 MCP transports connect and list tools
- [ ] Server auth works (OAuth, API key, bearer)
- [ ] Tool calls route through MCP correctly
- [ ] Resource reads work
- [ ] Prompt templates executable as commands
- [ ] Plugin install/uninstall with dependencies
- [ ] Version constraints resolved correctly
- [ ] Skills register as slash commands
- [ ] Skill eval framework runs tests
- [ ] Artifacts render in TUI
- [ ] Channels receive webhook events
- [ ] Permission prompts relay via channel