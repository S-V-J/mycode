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
Simply type `mycode` in any terminal. On the first run, it will prompt you to paste your NVIDIA API Key. This key is securely saved to `~/.mycode/.env` with strict `0600` POSIX permissions. You will never be asked for it again.

```bash
mycode
```

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