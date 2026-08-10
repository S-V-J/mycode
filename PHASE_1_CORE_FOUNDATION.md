# Phase 1: Core Agentic Foundation ✅ **COMPLETE**

**Goal:** Working autonomous coding agent with local-first architecture

## Completed Features (45 atomic items from 217 total)

### Agentic Loop (1)
- ✅ ReAct agentic loop (10 iterations max) with Thought→Action→Observation→Iteration

### Core Tools (6/15)
- ✅ `bash` - Sandboxed subprocess with 30s timeout, destructive command interception
- ✅ `read_file` - Read file with line numbers
- ✅ `write_file` - Write/overwrite files
- ✅ `edit_file` - Surgical diff replacement (search/replace blocks)
- ✅ `web_search` - DuckDuckGo search
- ✅ `fetch_url` - HTTP fetch with markdownify conversion
- ❌ Glob, Grep, LSP, Monitor, NotebookEdit, PowerShell, Agent, AskUserQuestion, EndConversation

### Operational Modes (6/6)
- ✅ **AUTO** - Full autonomous execution
- ✅ **PLAN** - Multi-step plan generation + TUI modal approval
- ✅ **MANUAL** - Pair-programmer mode (tools disabled)
- ✅ **AEROPLANE** - Offline mode (cache + RAG only, zero API calls)
- ✅ **DONT_ASK** - Auto-approve all actions (no permission prompts)
- ✅ **BYPASS_PERMISSIONS** - Skip all safety checks (execute any command)

### Streaming & Reasoning (1)
- ✅ Nemotron `enable_thinking` → `reasoning_content` stream (dim/italic) + content (Markdown)

### Semantic Caching (1)
- ✅ ChromaDB + SQLite with file-hash validation (MD5)
- ✅ Similarity threshold: >0.92 (hit), 0.85-0.92 (micro-validation), <0.85 (miss)
- ✅ Cache invalidation via Watchdog on file modify/create/delete

### Codebase RAG (1)
- ✅ Tree-sitter AST chunking (Python, JS, TS)
- ✅ Target nodes: function_definition, class_definition, function_declaration, class_declaration, method_definition, export_statement, lexical_declaration
- ✅ Watchdog live updates + cache invalidation integration

### Project Memory (1)
- ✅ MYCODE.md directory traversal injection into system prompt

### Session Persistence (1)
- ✅ SQLite sessions + messages with timestamps
- ✅ TUI sidebar session management (create/switch/delete)

### Security Sandbox (2)
- ✅ Destructive command interception (rm -rf, sudo, chmod 777, etc.)
- ✅ CWD restriction + 30s subprocess timeout

### Diff Approval (1)
- ✅ Unified diff in TUI modal (Accept Edits toggle F4)
- ✅ **acceptEdits** - Integrated as F4 toggle (Accept/Reject Edits)

### Dynamic Parameters (1)
- ✅ Smart routing: Base (temp=0.2, 4k tokens) vs Complex (temp=1.0, 16k tokens)
- ✅ Triggers: prompt>150chars, keywords (refactor, debug, security), iteration≥2

### Rate Limit Handling (1)
- ✅ Exponential backoff (5 attempts, 4-30s)
- ✅ Custom NVIDIA predicates (ResourceExhausted, Worker local)
- ✅ 1.5s cooldown after tool batches

### Global Install (1)
- ✅ `pipx install git+https://github.com/S-V-J/mycode.git`

### Privacy (1)
- ✅ All data local (SQLite, ChromaDB)
- ✅ API key in `~/.mycode/.env` (0600 permissions)

### Provider Agnostic (1)
- ✅ OpenAI-compatible endpoint (Nemotron, ready for Ollama/Together/OpenRouter)

### TUI Interface (1)
- ✅ Textual 3-column: Left (Chats/Sessions) | Center (Chat) | Right (File Tree)
- ✅ Modal dialogs: Plan approval, Diff approval
- ✅ Keybindings: F1 (Chats), F2 (Files), F3 (Mode), F4 (Edits), Ctrl+P (Palette), Ctrl+C (Quit)

### Multi-Session (1)
- ✅ SQLite-backed session management in left sidebar

### Status Bar (1)
- ✅ Shows: Mode, Accept Edits, Project name

---

## Files Implemented
- `src/mycode/cli.py` - Typer CLI entry point
- `src/mycode/tui/app.py` - Textual TUI application
- `src/mycode/core/agent.py` - ReAct loop, modes, routing
- `src/mycode/core/llm_client.py` - Nemotron streaming (two-phase)
- `src/mycode/core/cache.py` - Semantic cache + SQLite
- `src/mycode/core/rag.py` - Tree-sitter RAG + Watchdog
- `src/mycode/core/config.py` - API key vault + MYCODE.md discovery
- `src/mycode/core/modes.py` - AgentMode enum, approval logic
- `src/mycode/tools/schemas.py` - OpenAI tool schemas
- `src/mycode/tools/bash.py` - Sandboxed bash execution
- `src/mycode/tools/file_ops.py` - Read/Write/Edit operations
- `src/mycode/tools/web.py` - Web search + URL fetch

---

## Verification Checklist ✅
- [x] `mycode` starts, prompts for API key, saves to `~/.mycode/.env` (0600)
- [x] Streaming shows reasoning (dim/italic) → content (Markdown) without corruption
- [x] Tools execute: bash, read_file, write_file, edit_file, web_search, fetch_url
- [x] Modes toggle: F3 (AUTO→PLAN→MANUAL→AEROPLANE), F4 (Accept Edits)
- [x] Cache hit: Repeat query returns "Cache Hit" with sub-100ms response
- [x] Cache invalidation: Modify file → cache entries for that file invalidated
- [x] RAG context: Coding questions inject relevant codebase chunks
- [x] MYCODE.md: Project rules injected into system prompt
- [x] Sessions: F1 sidebar shows chat history, can switch/create/delete sessions
- [x] File tree: F2 sidebar shows live directory tree, updates on file changes
- [x] Plan mode: Tool batches show approval modal with step details
- [x] Diff approval: File writes show unified diff modal when Accept Edits = OFF
- [x] Aeroplane mode: Works offline using only cache + RAG
- [x] Global install: `pipx install git+https://github.com/S-V-J/mycode.git` works