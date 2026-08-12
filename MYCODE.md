# MyCode Project Rules

## Architecture & Standards
- This project is built using Python 3.10+ and follows PEP 8 standards.
- The core architecture is a ReAct agentic loop utilizing NVIDIA Nemotron for reasoning.
- All local state (caching, embeddings, history) is stored in `~/.mycode/`.
- **TUI Architecture (v2 - Complete):** IDE-like workspace with Setup Wizard → Left Sidebar (Multi-Project/Work History) → Center (Tabbed CLI Workspaces) → Right Sidebar (System Folder Manager). See `TUI_SPEC.md`.

## Preferred Libraries
- CLI: `typer`, `rich`
- TUI: `textual` (reactive widgets, CSS styling, command palette)
- Async/HTTP: `httpx`
- ML/Vector DB: `sentence-transformers`, `chromadb`
- Parsing: `tree-sitter`
- Config: `toml`
- JSON: `jsonschema` (payload validation), `pygments` (syntax highlighting)

## Tool Usage Rules
- When writing code, ALWAYS use the `write_file` tool.
- When modifying existing code, use `read_file` first to understand context, then `write_file` to overwrite.
- Never execute `rm -rf` or `sudo` commands without explicit user approval.

## TUI Workspace Rules (v2 - Complete)
- **Setup Wizard:** Must appear on first run; collects API key, provider, model, raw payload; saves to `~/.mycode/providers.json`
- **Multi-Project Sidebar:** Projects = trusted folders (explicit acknowledgment); Work Histories = editable chat sessions linked to projects; Ad-hoc = no project
- **Tabbed Workspaces:** Each tab = one work history; tabs know their project CWD; VS Code-style tab management
- **Trust Folders:** Per-work-project trusted system folders; acknowledgment dialog required; persists to `~/.mycode/trusted_folders.json`
- **Right Sidebar:** Folder tree per work project; context menu actions (Open, Read, Edit, Add to Context, Run Tests, Search)
- **Persistence:** `workspaces.json` (projects, histories, tabs), `config.toml` (UI prefs), `providers.json` (LLM profiles)
- **Keybindings:** F1 (left sidebar), F2 (right sidebar), F3 (mode), F4 (edits), Ctrl+T (new tab), Ctrl+W (close), Ctrl+Tab (next), Ctrl+Shift+P (palette), Ctrl+P (quick switch), Ctrl+Shift+F (search), Ctrl+K Ctrl+S (provider settings)
