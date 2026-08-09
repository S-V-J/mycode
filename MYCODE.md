# MyCode Project Rules

## Architecture & Standards
- This project is built using Python 3.10+ and follows PEP 8 standards.
- The core architecture is a ReAct agentic loop utilizing NVIDIA Nemotron for reasoning.
- All local state (caching, embeddings, history) is stored in `~/.mycode/`.

## Preferred Libraries
- CLI: `typer`, `rich`
- Async/HTTP: `httpx`
- ML/Vector DB: `sentence-transformers`, `chromadb`
- Parsing: `tree-sitter`

## Tool Usage Rules
- When writing code, ALWAYS use the `write_file` tool.
- When modifying existing code, use `read_file` first to understand context, then `write_file` to overwrite.
- Never execute `rm -rf` or `sudo` commands without explicit user approval.
