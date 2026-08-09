# MyCode: Open-Source Agentic CLI Development Masterplan

## 1. Executive Summary & Vision
**MyCode** is an open-source, locally-hosted, agentic CLI tool designed to replicate and extend the capabilities of proprietary tools like Claude Code. It operates entirely within the user's terminal (WSL/Linux/macOS), utilizing local Machine Learning for semantic caching, RAG (Retrieval-Augmented Generation) for codebase awareness, and configurable LLM endpoints (like NVIDIA Nemotron) for reasoning.

**Core Philosophy:** "Configure once, code forever." Users paste their API key once, and the CLI handles the rest, learning from every interaction to become faster and more accurate over time.

---

## 2. Feature Parity Research: Deconstructing Claude Code
To build a 100% functioning alternative, we must replicate the following core mechanics observed in state-of-the-art coding agents:

### A. The Agentic Loop (ReAct Pattern)
*   **Thought:** The model analyzes the request and formulates a plan (Extended Thinking).
*   **Action:** The model selects a tool (e.g., `read_file`, `execute_bash`).
*   **Observation:** The system executes the tool and returns the `stdout`/`stderr` to the model.
*   **Iteration:** The model evaluates the observation and decides whether to act again or provide the final answer.

### B. Core Tooling Capabilities
1.  **File Operations:** `read` (with line numbers), `write` (overwrite), `edit` (surgical diff replacement using search/replace blocks), `glob` (find files), `grep` (search contents).
2.  **Terminal Execution:** Sandboxed `bash` execution with timeout limits and environment isolation.
3.  **Self-Correction:** Automatically reading compiler/linter errors and writing fixes without user intervention.

### C. Context Window Management
*   **Dynamic Context Injection:** Instead of sending the whole repo, the agent uses tools to read *only* the necessary files.
*   **Summarization:** Compressing long terminal outputs to save tokens.

### D. Memory & State
*   **Project Memory (`CLAUDE.md` equivalent -> `MYCODE.md`):** A markdown file in the project root containing architecture rules, preferred libraries, and coding standards.
*   **Session State:** Remembering what files were changed during the current terminal session.

---

## 3. The "Bypass AI" Engine: Semantic Caching & Local ML
*Addressing your core requirement: "If this app can do the task using cache and database, it is not supposed to use the AI model."*

Yes, this is highly achievable and is called **Semantic Caching**. Here is how MyCode will implement it:

### The Interceptor Pipeline
1.  **Input Capture:** User types a prompt (e.g., "Write a pytest for the auth module").
2.  **Local Embedding:** A lightweight local ML model (`sentence-transformers/all-MiniLM-L6-v2`) converts the prompt into a vector embedding. *Cost: $0. Time: ~10ms.*
3.  **Vector Search:** The embedding is queried against a local **ChromaDB** vector database.
4.  **Similarity Threshold:**
    *   **Score > 0.95 (Exact/Semantic Match):** The system retrieves the cached "Trajectory" (the exact tool calls and final code generated last time). It executes the tool calls locally (if idempotent) or simply prints the cached final response. **The LLM API is completely bypassed.**
    *   **Score < 0.95 (Novel Task):** The prompt is forwarded to the NVIDIA Nemotron API.
5.  **Post-Execution Hook:** Once the novel task is completed successfully, the Prompt + Tool Trajectory + Final Code is embedded and saved to ChromaDB and a local **SQLite** database (for relational metadata like timestamps and success rates).

---

## 4. System Architecture & Tech Stack

| Component | Technology | Purpose |
| :--- | :--- | :--- |
| **CLI Interface** | `Rich`, `Prompt Toolkit`, `Typer` | Terminal UI, markdown rendering, multi-line input, auto-complete. |
| **Agentic Engine** | `PydanticAI` or Custom `ReAct` Loop | Tool schema validation, state management, API routing. |
| **Local ML/Embeddings** | `HuggingFace SentenceTransformers` | Converting text to vectors locally for caching and RAG. |
| **Vector Database** | `ChromaDB` | Storing prompt embeddings and codebase chunks for semantic search. |
| **Relational DB** | `SQLite` | Storing chat history, tool execution logs, and user configs. |
| **Code Parsing** | `Tree-sitter` | AST parsing for intelligent code chunking and context retrieval. |
| **File Watching** | `Watchdog` | Monitoring the filesystem for changes to update the local RAG index. |

---

## 5. Phased Development Roadmap & AI Prompts

### Phase 1: Core CLI, Streaming & Configuration
**Goal:** Establish the terminal UI, handle API keys securely, and fix streaming.
*   **Research/Context:** `rich.console.Console.print()` does not support `flush=True`. We must use `rich.live` or standard `sys.stdout` for streaming.
*   **Prompt 1 (Streaming UI):** "Write a Python CLI using `Typer` and `Rich`. Implement a streaming function using `httpx` to connect to an OpenAI-compatible API. Use `rich.live.Live` and `rich.markdown.Markdown` to render the streaming text in real-time. Ensure the terminal cursor is hidden during generation and restored on exit."
*   **Prompt 2 (Secure Config):** "Implement a configuration manager using `python-dotenv` and `pathlib`. On first run, if `NVIDIA_API_KEY` is missing from `~/.mycode/.env`, prompt the user securely to paste it. Save it with `0600` file permissions so only the user can read it."

### Phase 2: Agentic Tool Loop & Sandbox
**Goal:** Give the AI "hands" to interact with the WSL filesystem and terminal.
*   **Research/Context:** Tools must be defined as Pydantic models or JSON schemas so the LLM knows how to call them.
*   **Prompt 3 (Tool Execution):** "Define Pydantic models for three tools: `BashTool(command: str)`, `ReadTool(file_path: str)`, and `WriteTool(file_path: str, content: str)`. Create an execution loop that intercepts these tool calls from the LLM, executes them using `subprocess` (for bash) and `pathlib` (for files), and feeds the `stdout` or file content back to the LLM as a `tool` role message."
*   **Prompt 4 (Safety & Permissions):** "Implement a safety interceptor in the tool execution loop. If the `BashTool` command contains destructive keywords (`rm -rf`, `sudo`, `chmod 777`, `mkfs`), pause execution. Use `rich.prompt.Confirm` to ask the user for explicit permission before proceeding."

### Phase 3: The Semantic Cache & Local ML (The "Bypass" Engine)
**Goal:** Implement the local database to bypass the AI model for repeated tasks.
*   **Research/Context:** ChromaDB is perfect for local, persistent vector storage.
*   **Prompt 5 (Cache Interceptor):** "Setup a local ChromaDB collection. Integrate `sentence-transformers` to load `all-MiniLM-L6-v2`. Before calling the LLM, generate an embedding of the user's prompt. Query ChromaDB. If a match exists with a cosine similarity > 0.95, print a '[green]Cache Hit: Bypassing LLM[/green]' message and return the stored response trajectory."
*   **Prompt 6 (Post-Execution Hook):** "Write a post-execution hook. Once a task is successfully completed, serialize the user prompt, the tool calls made, and the final code output. Generate an embedding and save this trajectory to ChromaDB. Also, save the raw text to a local SQLite database (`history.db`) for standard chat history retrieval."

### Phase 4: Codebase Indexing & RAG (Retrieval-Augmented Generation)
**Goal:** Make the AI aware of the user's entire project without overflowing the context window.
*   **Research/Context:** Naively reading all files fails on large repos. We need AST-based chunking.
*   **Prompt 7 (Background Indexer):** "Create a background worker using `watchdog` that monitors the current WSL directory for `.py`, `.js`, `.ts`, and `.md` files. Use `tree-sitter` to parse these files into logical chunks (functions, classes). Embed these chunks and store them in a separate ChromaDB collection named `codebase_index`."
*   **Prompt 8 (Auto-Context Retriever):** "Implement an 'Auto-Context' retriever. When the user asks a coding question, search the `codebase_index` for the top 5 most relevant code chunks. Inject these chunks into the system prompt dynamically before sending the request to the LLM, ensuring the AI has the exact context it needs."

### Phase 5: Global Installation, Memory & `MYCODE.md`
**Goal:** Make it a globally accessible command and implement project-specific memory.
*   **Research/Context:** `pyproject.toml` with `[project.scripts]` allows global CLI installation via `pip install -e .`.
*   **Prompt 9 (Global CLI & Memory):** "Configure a `pyproject.toml` file with a `[project.scripts]` entry point mapping `mycode` to the main CLI function. Implement logic to search the current working directory and its parents for a `MYCODE.md` file. If found, read its contents and inject it into the system prompt as strict project rules and architectural guidelines."

---

## 6. WSL-Specific Considerations & Fixes
Since you are operating in **WSL (Windows Subsystem for Linux)**, specific edge cases must be handled:
1.  **File Watchers (inotify limits):** WSL2 sometimes struggles with `watchdog` due to `inotify` limits. *Fix:* Add a script to increase `fs.inotify.max_user_watches` via `sysctl`.
2.  **Path Translation:** If executing Windows binaries from WSL, paths must be translated (e.g., `/mnt/c/`). *Fix:* Force all internal tool executions to use strict POSIX `pathlib.Path` objects and restrict executions to the Linux filesystem (`~/` or `/home/`) for maximum I/O performance.
3.  **Terminal Sizing:** WSL terminal resizing can break `Rich` live displays. *Fix:* Implement a `signal.signal(signal.SIGWINCH, handler)` to catch terminal resize events and redraw the `Rich` layout.

---

## 7. Next Steps for Execution
To begin building this from scratch, follow this exact sequence:
1.  Initialize a new Python project: `mkdir mycode && cd mycode && python -m venv venv && source venv/bin/activate`.
2.  Install base dependencies: `pip install typer rich httpx python-dotenv pydantic`.
3.  Execute **Prompt 1 & 2** to get the basic streaming shell working.
4.  Once the shell works, proceed to **Phase 2** to give it tool-calling capabilities.