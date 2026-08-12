# MyCode 🚀

**An open-source, locally-hosted agentic CLI for autonomous coding.**

MyCode is a privacy-focused, extensible alternative to proprietary AI coding assistants (like Claude Code). It operates entirely within your terminal, utilizing local Machine Learning for semantic caching, Retrieval-Augmented Generation (RAG) for deep codebase awareness, and configurable LLM endpoints for reasoning.

## 🌟 Core Philosophy
*"Configure once, code forever."* 
Paste your API key once, and the CLI handles the rest—learning from every interaction to become faster and more accurate over time.

## ✨ Key Features
- **🧠 Semantic Caching ("Bypass AI"):** Uses local vector embeddings to instantly retrieve solutions for previously solved tasks, bypassing API calls and saving costs.
- **🛠️ Agentic Tool Loop:** Autonomous execution of Bash commands, file reading/writing, and surgical code editing via a secure ReAct loop.
- **📂 Local RAG & Codebase Indexing:** Intelligently parses and indexes your local repository using Tree-sitter, providing the LLM with exact context without overflowing the token limit.
- **📖 Project Memory (`MYCODE.md`):** Automatically detects and injects project-specific rules and architectural guidelines into the AI's system prompt.
- **🔒 Privacy & Security First:** All caching, embeddings, and execution logs are stored locally in SQLite and ChromaDB. Destructive terminal commands require explicit user approval.
- **🔌 Provider Agnostic:** Pre-configured for NVIDIA Nemotron, but easily adaptable to any OpenAI-compatible API (Ollama, Together AI, OpenRouter).
- **🖥️ IDE-like TUI Workspace (v2 Complete):** Multi-project sidebar, tabbed CLI workspaces (VS Code-style), trust-based folder access, per-project system folder manager — see `TUI_SPEC.md`

## 🚀 Global Installation

MyCode is designed to be installed globally using `pipx`, which creates an isolated environment and symlinks the `mycode` command to your system PATH.

### Prerequisites
- Python 3.10 or higher
- [pipx](https://pypa.github.io/pipx/) installed (`python3 -m pip install --user pipx && python3 -m pipx ensurepath`)

### Install from GitHub
```bash
pipx install git+https://github.com/S-V-J/mycode.git
```

### First Run Configuration
On first run, MyCode launches a **Setup Wizard** (TUI modal) that guides you through:
1. **API Key** — Securely saved to `~/.mycode/.env` (0600 permissions)
2. **Provider Selection** — NVIDIA Nemotron, OpenAI, Ollama, Together AI, OpenRouter, or Custom URL
3. **Model Selection** — Fetched live from provider's `/models` endpoint
4. **Raw Payload Editor** — Full JSON payload with provider-specific defaults (temperature, max_tokens, reasoning_budget, etc.), fully editable

All settings persist to `~/.mycode/providers.json` for multi-profile support.

## 🏗️ Development Status

**Current Version:** v0.7.0 (Phases 1-5 Complete - 75% of total roadmap)

| Phase | Status | Features |
|-------|--------|----------|
| **Phase 1: Core Foundation** | ✅ Complete | ReAct agent, 8 tools, 6 modes, semantic cache, RAG, TUI (v2) |
| **Phase 2: Hooks & Automation** | ✅ Complete | 31 hook events, 5 handlers, scheduler, checkpoints, headless |
| **Phase 3: MCP & Plugins** | ✅ Complete | 4 MCP transports, plugin marketplace, skills, artifacts, channels |
| **Phase 4: Multi-Surface** | 📋 Planned | Desktop, Web, Mobile, VS Code, JetBrains, Chrome, Slack |
| **Phase 5: TUI Redesign + Intelligence** | ✅ Complete | Setup wizard, multi-project sidebar, tabbed workspaces, trust folders, prompt library, Vim mode, themes, analytics, advisor, fast mode |

See [DEVELOPMENT_PHASES.md](./DEVELOPMENT_PHASES.md) for detailed status.

## 📖 Usage & Project Memory

### Basic Usage
Navigate to any project directory and run `mycode`. The CLI will automatically index your codebase for RAG context in the background.

### Project Rules (`MYCODE.md`)
To give MyCode specific instructions about your project (e.g., preferred libraries, architectural patterns, testing frameworks), create a file named `MYCODE.md` in the root of your repository. MyCode will automatically traverse up your directory tree, find this file, and inject its contents into the AI's system prompt.

Example `MYCODE.md`:
```markdown
# Project Rules
- Always use Pydantic V2 for data validation.
- Prefer `pytest` over `unittest`.
- When writing React components, use Tailwind CSS.
```

## 💖 Support & Sponsors

If you find MyCode useful and want to support its ongoing development, please consider sponsoring the project! Your contributions help fund local ML research, server costs, and keep MyCode 100% open-source.

<a href="https://github.com/sponsors/S-V-J">
  <img src="https://img.shields.io/badge/Sponsor-S--V--J-blue?logo=github&style=for-the-badge" alt="Sponsor S-V-J" height="35">
</a>

> **Note for Webmasters:** If you are hosting documentation for MyCode on an external site (like GitHub Pages or a personal blog), you can embed the official sponsor card using the following HTML:
> ```html
> <iframe src="https://github.com/sponsors/S-V-J/card" title="Sponsor S-V-J" height="225" width="600" style="border: 0;"></iframe>
> ```

## 📖 Documentation & Roadmap
This project is being built in public. See the [MyCode Masterplan](./MyCode_Masterplan.md) for the complete architectural roadmap, tech stack, and development phases.

## 🤝 Contributing
This is an open-source product. We welcome contributions! Please check the Masterplan roadmap to see where you can help.

## 📄 License
MIT License