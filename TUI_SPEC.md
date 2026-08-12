# MyCode TUI Workspace Specification (v2)

**Version:** 2.0  
**Status:** 📋 Planned (Phase 5)  
**Target:** Complete IDE-like terminal workspace replacing current 3-column TUI (v1)

---

## 1. Overview

The TUI v2 transforms MyCode from a simple chat interface into a full-featured **IDE-like terminal workspace** with:

- **Setup Wizard** — First-run configuration (API key, provider, model, raw payload)
- **Left Sidebar** — Multi-project & work history manager (trusted folders, editable sessions)
- **Center** — Tabbed CLI workspaces (VS Code-style tabs, each with project context)
- **Right Sidebar** — System folder manager per work project (trust acknowledgment, context actions)
- **Persistence Layer** — JSON/TOML configs for providers, workspaces, trusted folders, UI preferences

---

## 2. Architecture

### 2.1 High-Level Component Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                            MyCode TUI App (Textual)                         │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌──────────────────┐  ┌────────────────────────┐  ┌────────────────────┐  │
│  │  LEFT SIDEBAR    │  │      CENTER TABS       │  │  RIGHT SIDEBAR     │  │
│  │  (Dockable, F1)  │  │  (TabbedContent)       │  │  (Dockable, F2)    │  │
│  ├──────────────────┤  ├────────────────────────┤  ├────────────────────┤  │
│  │ ProjectTree      │  │ Tab 1: Work History A  │  │ FolderTree         │  │
│  │ ├─ Project 1     │  │ ├─ Chat Messages       │  │ ├─ /trusted/path   │  │
│  │ │  ├─ History 1  │  │ ├─ Tool Executions     │  │ │  ├─ src/         │  │
│  │ │  ├─ History 2  │  │ └─ Input Area          │  │ │  └─ tests/       │  │
│  │ │  └─ + New      │  │                        │  │ └─ Context Menu    │  │
│  │ ├─ Project 2     │  │ Tab 2: Work History B  │  │    (Open, Read,    │  │
│  │ └─ (No Project)  │  │ └─ ...                 │  │     Edit, Test,    │  │
│  │                  │  │                        │  │     Search)        │  │
│  └──────────────────┘  └────────────────────────┘  └────────────────────┘  │
│                                                                             │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │                        MODAL LAYER (Overlay)                         │  │
│  │  • Setup Wizard (first run)     • Trust Folder Dialog               │  │
│  │  • Plan Approval Modal          • Diff Approval Modal               │  │
│  │  • Provider Settings Modal      • Command Palette (Ctrl+Shift+P)    │  │
│  │  • Raw Payload Editor           • Cross-History Search (Ctrl+Shift+F)│  │
│  └──────────────────────────────────────────────────────────────────────┘  │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 2.2 Data Models

```python
# ~/.mycode/providers.json
{
  "profiles": [
    {
      "id": "uuid",
      "name": "NVIDIA Nemotron",
      "api_key": "encrypted_or_plain",
      "base_url": "https://integrate.api.nvidia.com/v1",
      "model": "nvidia/nemotron-3-ultra",
      "raw_payload": {
        "model": "nvidia/nemotron-3-ultra",
        "temperature": 0.2,
        "max_tokens": 4096,
        "enable_thinking": true,
        "reasoning_budget": 2048
      },
      "is_default": true,
      "created_at": "2024-01-15T10:30:00Z"
    }
  ],
  "active_profile_id": "uuid"
}

# ~/.mycode/workspaces.json
{
  "projects": [
    {
      "id": "uuid",
      "name": "mycode-project",
      "trusted_folder": "/home/user/code/mycode",
      "trusted_at": "2024-01-15T10:30:00Z",
      "work_histories": [
        {
          "id": "uuid",
          "name": "Fix auth bug",
          "session_id": "sqlite-session-uuid",
          "project_id": "project-uuid",
          "created_at": "2024-01-15T10:30:00Z",
          "updated_at": "2024-01-15T14:30:00Z",
          "is_active": true
        }
      ]
    }
  ],
  "ad_hoc_histories": [
    {
      "id": "uuid",
      "name": "Quick test",
      "session_id": "sqlite-session-uuid",
      "created_at": "2024-01-15T16:20:00Z",
      "updated_at": "2024-01-15T16:20:00Z"
    }
  ],
  "tab_state": {
    "active_tab_id": "uuid",
    "tabs": [
      {"id": "uuid", "work_history_id": "uuid", "title": "Fix auth bug", "dirty": false}
    ]
  },
  "ui_preferences": {
    "theme": "dark",
    "left_sidebar_open": true,
    "right_sidebar_open": true,
    "font_size": 14
  }
}

# ~/.mycode/trusted_folders.json
{
  "folders": [
    {
      "path": "/home/user/code/mycode",
      "project_id": "project-uuid",
      "acknowledged_at": "2024-01-15T10:30:00Z",
      "permissions": ["read", "write", "execute", "index"]
    }
  ]
}

# ~/.mycode/config.toml
[ui]
theme = "dark"
font_size = 14
animations = true

[keybindings]
# Custom keybindings can override defaults
# "ctrl+t" = "new_tab"

[provider]
auto_fetch_models = true
default_temperature = 0.2

---

## 3. First-Run Setup Wizard

### 3.1 Flow
```
Launch mycode
    │
    ▼
┌─────────────────────────────────────┐
│  No ~/.mycode/providers.json?       │
│  ▼ YES                              │
│  Show Setup Wizard (Modal)          │
│  ▼                                  │
│  Step 1: API Key Input              │
│  Step 2: Provider Selection         │
│  Step 3: Model Selection            │
│  Step 4: Raw Payload Editor         │
│  Step 5: Save & Launch              │
│  ▼                                  │
│  Write providers.json               │
│  Write .env (API key, 0600)         │
│  ▼                                  │
│  Launch Main TUI                    │
└─────────────────────────────────────┘
```

### 3.2 Step Details

#### Step 1: API Key
- Masked input (password field)
- Validation: non-empty, basic format check
- Saved to `~/.mycode/.env` with `0600` permissions

#### Step 2: Provider Selection
```
┌─────────────────────────────────────────────────────────────┐
│  Select Provider                                            │
├─────────────────────────────────────────────────────────────┤
│  ○ NVIDIA Nemotron      https://integrate.api.nvidia.com/v1 │
│  ○ OpenAI               https://api.openai.com/v1           │
│  ○ Ollama (Local)       http://localhost:11434/v1           │
│  ○ Together AI          https://api.together.xyz/v1         │
│  ○ OpenRouter           https://openrouter.ai/api/v1        │
│  ○ Custom...            [________________________________]  │
│                                                             │
│  [Back]                                    [Next >]         │
└─────────────────────────────────────────────────────────────┘
```
- Default providers with pre-filled base URLs
- Custom option shows URL input field
- Fetch `/models` endpoint on selection (async, with loading indicator)

#### Step 3: Model Selection
```
┌─────────────────────────────────────────────────────────────┐
│  Select Model (NVIDIA Nemotron)                             │
├─────────────────────────────────────────────────────────────┤
│  ▼ nvidia/nemotron-3-ultra          [Refresh Models]        │
│    nvidia/nemotron-3-ultra                                    │
│    nvidia/nemotron-4-340b                                     │
│    nvidia/nemotron-3-8b                                       │
│    Custom model ID... [________________________________]    │
│                                                             │
│  [Back]                                    [Next >]         │
└─────────────────────────────────────────────────────────────┘
```
- Populated from provider's `/models` endpoint
- Fallback to known models if fetch fails
- Custom model ID input

#### Step 4: Raw Payload Editor
```
┌─────────────────────────────────────────────────────────────┐
│  Raw Payload (JSON) — Editable                              │
├─────────────────────────────────────────────────────────────┤
│  {                                                          │
│    "model": "nvidia/nemotron-3-ultra",                      │
│    "temperature": 0.2,                                      │
│    "max_tokens": 4096,                                      │
│    "enable_thinking": true,                                 │
│    "reasoning_budget": 2048,                                │
│    "top_p": 0.95,                                           │
│    "frequency_penalty": 0.0,                                │
│    "presence_penalty": 0.0                                  │
│  }                                                          │
│                                                             │
│  [Validate JSON]  [Reset to Defaults]                       │
│                                                             │
│  [Back]                                    [Launch >]       │
└─────────────────────────────────────────────────────────────┘
```
- Pre-filled with provider-specific defaults
- Full JSON editor with syntax highlighting (Pygments)
- Real-time JSON validation
- "Reset to Defaults" button
- Schema validation against provider capabilities

#### Step 5: Save & Launch
- Write `providers.json` with profile
- Write `.env` with API key
- Close wizard, launch main TUI

### 3.3 Re-accessing Settings
- Command Palette (Ctrl+Shift+P) → "Configure Provider"
- Opens same wizard pre-filled with current profile
- Allows switching profiles, adding new ones

---

## 4. Left Sidebar — Multi-Project & Work History Manager

### 4.1 Widget Structure
```python
class ProjectTree(Static):
    """Left sidebar: Projects + Work Histories"""
    
    COMPONENTS = [
        Header("PROJECTS & WORKSPACES", actions=[AddProjectButton]),
        ProjectTreeView(),           # Tree: Project → Work Histories
        AdHocSection(),              # "No Project" histories
        Footer(actions=[AddFolderButton, ManageTrustButton])
    ]
```

### 4.2 Visual Layout
```
┌────────────────────────────────────────────────────────────┐
│  📁 PROJECTS & WORKSPACES                    [➕ New]     │
├────────────────────────────────────────────────────────────┤
│  📂 mycode-project (trusted: /home/user/code/mycode) ✓   │
│     ├─ 💬 "Fix auth bug"          [2024-01-15 14:30]     │
│     ├─ 💬 "Refactor agent loop"   [2024-01-14 09:12]     │
│     ├─ 💬 *Untitled*              [2024-01-13 22:45]     │
│     └─ ➕ New Work History...                               │
│                                                             │
│  📂 client-api (trusted: /home/user/work/client-api) ✓   │
│     ├─ 💬 "Add rate limiting"     [2024-01-15 10:00]     │
│     └─ ➕ New Work History...                               │
│                                                             │
│  📂 (No Project) — Ad-hoc work                             │
│     ├─ 💬 "Quick test"          [2024-01-15 16:20]       │
│                                                             │
│  [📂 Add Project Folder...]  [⚙️ Manage Trust Folders]   │
└────────────────────────────────────────────────────────────┘
```

### 4.3 Interactions
| Action | Trigger | Behavior |
|--------|---------|----------|
| Select work history | Click / Enter | Opens/closes tab in center |
| Rename | Double-click / F2 / Context menu | Inline edit, persist to JSON |
| Delete | Delete key / Context menu | Confirm modal, remove from JSON + SQLite |
| New work history | "➕ New Work History" / Ctrl+N | Create session, add to project |
| Add project folder | "📂 Add Project Folder..." | Folder picker → trust dialog → add |
| Manage trust | "⚙️ Manage Trust Folders" | Opens trust folder manager modal |
| Toggle sidebar | F1 | Collapse/expand |

### 4.4 Project Creation Flow
```
Click "Add Project Folder"
    ▼
Native folder picker (or path input)
    ▼
Select folder → Check if already trusted
    ▼
If NOT trusted → Show Trust Acknowledgment Dialog
    ▼
User clicks "Allow & Trust" + "Remember"
    ▼
Add to trusted_folders.json + workspaces.json
    ▼
Create project entry in ProjectTree
    ▼
Auto-create first work history ("Untitled")
```

---

## 5. Center — Tabbed CLI Workspaces

### 5.1 Widget Structure
```python
class CenterTabs(TabbedContent):
    """VS Code-style tabbed workspaces"""
    
    TABS = [
        TabPane(
            work_history_id="uuid",
            title="Fix auth bug",
            dirty=False,
            content=ChatWorkspace(project_cwd="/home/user/code/mycode")
        ),
        # ... more tabs
    ]
    
    ACTIONS = [
        NewTabAction,          # Ctrl+T
        CloseTabAction,        # Ctrl+W
        NextTabAction,         # Ctrl+Tab
        PrevTabAction,         # Ctrl+Shift+Tab
        SplitTabAction,        # Ctrl+Shift+S
        DuplicateTabAction,    # Ctrl+Shift+D
        RenameTabAction,       # F2 on tab
        CloseOthersAction,     # Context menu
    ]
```

### 5.2 ChatWorkspace Widget
```python
class ChatWorkspace(Vertical):
    """Single tab content: chat + input"""
    
    COMPONENTS = [
        MessageList(),      # Scrollable: user/assistant/tool messages
        ToolCallView(),     # Live tool execution display
        InputArea(),        # TextArea with Ctrl+Enter to send
    ]
```

### 5.3 Visual Layout
```
┌────────────────────────────────────────────────────────────────┐
│  [💬 Fix auth bug ▼]  [💬 Refactor agent ▼]  [💬 Quick test ▼]  [+] │
├────────────────────────────────────────────────────────────────┤
│                                                                │
│  ┌────────────────────────────────────────────────────────┐   │
│  │  **You:** Fix the authentication bug in login flow     │   │
│  │                                                          │   │
│  │  **MyCode:** I'll analyze the auth module...           │   │
│  │  ┌─[bash] Reading src/auth/login.py                    │   │
│  │  │ $ cat src/auth/login.py                              │   │
│  │  └────────────────────────────────────────────────────┘   │   │
│  │  [edit_file] Applying fix...                           │   │
│  │  **MyCode:** Fixed! The issue was...                   │   │
│  │                                                          │   │
│  │  ────────────────────────────────────────────────────  │   │
│  │  **You:** (next input)                                 │   │
│  └────────────────────────────────────────────────────────┘   │
│                                                                │
│  ┌────────────────────────────────────────────────────────┐   │
│  │  [TextArea: Type message... Ctrl+Enter to send]       │   │
│  └────────────────────────────────────────────────────────┘   │
└────────────────────────────────────────────────────────────────┘
```

### 5.4 Tab Context Awareness
- Each tab stores `project_id` (or `null` for ad-hoc)
- On tab activation: set agent CWD to project's trusted folder
- Tools (`bash`, `read_file`, `write_file`, `edit_file`, `glob`, `grep`) execute in that CWD
- RAG indexing uses project folder
- Status bar shows current project name

### 5.5 Tab Management
| Action | Shortcut | Behavior |
|--------|----------|----------|
| New tab | Ctrl+T | Create new work history (prompts for project) |
| Close tab | Ctrl+W | Close current (prompt if dirty) |
| Next tab | Ctrl+Tab | Cycle forward |
| Prev tab | Ctrl+Shift+Tab | Cycle backward |
| Split tab | Ctrl+Shift+S | Split view (horizontal/vertical) |
| Duplicate | Ctrl+Shift+D | Clone tab with same history |
| Rename | F2 on tab | Inline edit tab title |
| Reorder | Drag tab | Drag to reorder |
| Close others | Right-click → Close Others | Keep only this tab |

---

## 6. Right Sidebar — System Folder Manager

### 6.1 Widget Structure
```python
class FolderManager(Static):
    """Right sidebar: Folder tree per work project"""
    
    COMPONENTS = [
        Header("SYSTEM FOLDER", actions=[TrustSettingsButton, RefreshButton]),
        FolderTree(),              # Tree-sitter aware file tree
        ContextMenu(),             # Right-click actions
    ]
```

### 6.2 Visual Layout
```
┌────────────────────────────────────────────────────────────┐
│  📂 SYSTEM FOLDER: /home/user/code/mycode (Trusted ✓)     │
│  [🔒 Trust Settings]  [🔄 Refresh]                         │
├────────────────────────────────────────────────────────────┤
│  📁 src/                                                   │
│  ┌ 📁 core/                                                │
│  │  ┌ 📄 agent.py          ▸                               │
│  │  ┌ 📄 cache.py          ▸                               │
│  │  └ 📄 rag.py           ▸                               │
│  ┌ 📁 tools/                                              │
│  ┌ 📁 tui/                                                │
│  📁 tests/                                                 │
│  📄 README.md                                             │
│  📄 pyproject.toml                                        │
│                                                             │
│  [Context menu on right-click:]                            │
│  ▸ Open in Editor                                          │
│  ▸ Read File                                               │
│  ▸ Edit File                                               │
│  ▸ Delete                                                  │
│  ▸ Copy Path                                               │
│  ▸ Add to Context (RAG)                                    │
│  ▸ Run Tests (if test file)                                │
│  ▸ Search in Folder                                        │
└────────────────────────────────────────────────────────────┘
```

### 6.3 Trust Acknowledgment Flow
```
User adds new project folder
    ▼
┌────────────────────────────────────────────────────────────┐
│  🔒 Trust Folder Required                                  │
├────────────────────────────────────────────────────────────┤
│  MyCode needs access to: /home/user/code/mycode            │
│                                                             │
│  This allows:                                               │
│  • Reading/writing files in this folder                    │
│  • Running bash commands in this folder                    │
│  • Indexing code for RAG context                           │
│                                                             │
│  [ ] Remember this folder (add to trusted list)           │
│                                                             │
│  [Deny]                    [Allow & Trust]                 │
└────────────────────────────────────────────────────────────┘
    ▼
If "Allow & Trust" + "Remember" checked:
    ▼
Write to trusted_folders.json:
{
  "path": "/home/user/code/mycode",
  "project_id": "uuid",
  "acknowledged_at": "2024-01-15T10:30:00Z",
  "permissions": ["read", "write", "execute", "index"]
}
    ▼
Start Watchdog watcher for this folder
Start RAG indexing for this folder
```

### 6.4 Context Menu Actions
| Action | Implementation |
|--------|----------------|
| Open in Editor | Launch `$EDITOR` or `code` with file path |
| Read File | `read_file` tool → show in modal |
| Edit File | Open `edit_file` diff modal |
| Delete | Confirm → `bash rm` → refresh tree |
| Copy Path | Copy absolute path to clipboard |
| Add to Context | Trigger RAG re-index for file, inject into current chat |
| Run Tests | Detect test framework → `bash pytest <file>` |
| Search in Folder | Open search modal scoped to folder |

---

## 7. Persistence Layer Details

### 7.1 File Locations
```
~/.mycode/
├── .env                    # API keys (0600)
├── providers.json          # LLM provider profiles
├── workspaces.json         # Projects, histories, tabs, UI prefs
├── trusted_folders.json    # Acknowledged folders
├── config.toml             # UI settings, keybindings
├── history.db              # SQLite: sessions, messages, trajectories
├── chroma_data/            # ChromaDB: semantic cache trajectories
└── rag_data/               # ChromaDB: codebase index
```

### 7.2 Load/Save Strategy
- **Startup:** Load all JSON/TOML → populate widgets → restore tab state
- **On Change:** Debounced save (500ms) for `workspaces.json`, `config.toml`
- **Immediate Save:** `providers.json`, `trusted_folders.json`, `.env`
- **Shutdown:** Force save all

### 7.3 Migration
- Version field in each JSON file
- Migration functions for schema changes
- Backup before migration

---

## 8. Keyboard Shortcuts (Complete)

| Shortcut | Action | Context |
|----------|--------|---------|
| **F1** | Toggle left sidebar | Global |
| **F2** | Toggle right sidebar | Global |
| **F3** | Cycle AI Mode | Global |
| **F4** | Toggle Accept Edits | Global |
| **Ctrl+T** | New tab (work history) | Center |
| **Ctrl+W** | Close current tab | Center |
| **Ctrl+Tab** | Next tab | Center |
| **Ctrl+Shift+Tab** | Previous tab | Center |
| **Ctrl+Shift+P** | Command Palette | Global |
| **Ctrl+P** | Quick Switch Work History | Global |
| **Ctrl+Shift+F** | Search Across Histories | Global |
| **Ctrl+K, Ctrl+S** | Open Provider Settings | Global |
| **Ctrl+N** | New Work History (in project) | Left Sidebar |
| **Delete** | Delete selected item | Left/Right Sidebar |
| **F2** (on item) | Rename | Left Sidebar tabs, Right Sidebar files |
| **Enter** | Open/Activate | Left Sidebar histories, Right Sidebar files |
| **Right-click** | Context Menu | All sidebars, tabs, files |
| **Ctrl+Enter** | Send Message | Input Area |
| **Escape** | Close Modal / Cancel | Modals, Input |
| **Ctrl+Shift+S** | Split Tab | Center Tabs |
| **Ctrl+Shift+D** | Duplicate Tab | Center Tabs |

---

## 9. Textual Widget Structure (Implementation)

### 9.1 File Layout
```
src/mycode/tui/
├── app.py                      # Main App class
├── app.tcss                    # Global styles
├── keybindings.py              # Keybinding definitions
├── css/
│   ├── layout.tcss             # Grid/flex layout
│   ├── sidebar.tcss            # Sidebar styles
│   ├── tabs.tcss               # Tab styles
│   ├── modals.tcss             # Modal styles
│   └── syntax.tcss             # Syntax highlighting
├── widgets/
│   ├── __init__.py
│   ├── left_sidebar/
│   │   ├── __init__.py
│   │   ├── project_tree.py     # ProjectTree widget
│   │   ├── project_node.py     # Project tree node
│   │   ├── history_node.py     # Work history tree node
│   │   ├── ad_hoc_section.py   # Ad-hoc histories
│   │   └── add_project_dialog.py
│   ├── center/
│   │   ├── __init__.py
│   │   ├── tabbed_workspace.py # TabbedContent subclass
│   │   ├── chat_workspace.py   # Single tab content
│   │   ├── message_list.py     # Chat messages
│   │   ├── tool_call_view.py   # Live tool display
│   │   ├── input_area.py       # TextArea with shortcuts
│   │   └── tab_bar.py          # Custom tab bar
│   ├── right_sidebar/
│   │   ├── __init__.py
│   │   ├── folder_manager.py   # FolderManager widget
│   │   ├── folder_tree.py      # File tree with tree-sitter
│   │   ├── folder_node.py      # File/folder tree node
│   │   └── context_menu.py     # Right-click menu
│   ├── modals/
│   │   ├── __init__.py
│   │   ├── setup_wizard.py     # Multi-step wizard
│   │   ├── trust_dialog.py     # Trust acknowledgment
│   │   ├── plan_approval.py    # Plan mode approval
│   │   ├── diff_approval.py    # Diff approval
│   │   ├── payload_editor.py   # Raw payload JSON editor
│   │   ├── provider_settings.py # Provider config modal
│   │   ├── command_palette.py  # Ctrl+Shift+P
│   │   └── search_modal.py     # Cross-history search
│   └── shared/
│       ├── __init__.py
│       ├── status_bar.py       # Bottom status bar
│       ├── toast.py            # Notifications
│       └── confirm_dialog.py   # Generic confirm
```

### 9.2 Key Widget Classes

```python
# app.py
class MyCodeApp(App):
    CSS_PATH = "app.tcss"
    BINDINGS = load_keybindings()  # From keybindings.py
    
    def compose(self):
        yield Header()
        yield LeftSidebar(id="left-sidebar")
        yield CenterTabs(id="center-tabs")
        yield RightSidebar(id="right-sidebar")
        yield StatusBar(id="status-bar")
        yield Footer()
    
    def on_mount(self):
        self.load_workspace_state()
        if not providers_exist():
            self.push_screen(SetupWizard())
    
    def load_workspace_state(self):
        # Load workspaces.json → restore projects, histories, tabs
        pass
    
    def save_workspace_state(self):
        # Debounced save to workspaces.json
        pass

# left_sidebar/project_tree.py
class ProjectTree(Static):
    def compose(self):
        yield Tree("PROJECTS & WORKSPACES", id="project-tree")
        yield Button("Add Project Folder", id="add-project", variant="primary")
        yield Button("Manage Trust Folders", id="manage-trust")
    
    def on_tree_node_selected(self, event):
        if event.node.data.get("type") == "work_history":
            self.app.open_work_history(event.node.data["id"])

# center/tabbed_workspace.py
class CenterTabs(TabbedContent):
    def add_work_history(self, history_id, title, project_id):
        pane = TabPane(
            ChatWorkspace(history_id, project_id),
            title=title,
            id=f"tab-{history_id}"
        )
        self.add_pane(pane)
    
    def on_tab_activated(self, event):
        # Set agent CWD to tab's project folder
        self.app.set_active_project(event.pane.project_id)

# right_sidebar/folder_manager.py
class FolderManager(Static):
    def compose(self):
        yield FolderTree(path=self.app.get_active_project_folder())
    
    def watch_active_project(self, project):
        self.query_one(FolderTree).set_path(project.trusted_folder)
```

---

## 10. CSS Layout (app.tcss)

```css
/* app.tcss - Main Layout */
Screen {
    layout: horizontal;
    background: $surface;
}

#left-sidebar {
    width: 30%;
    max-width: 40;
    min-width: 25;
    border-right: solid $primary 1;
    height: 100%;
    layout: vertical;
}

#center-tabs {
    width: 1fr;
    height: 100%;
    layout: vertical;
}

#right-sidebar {
    width: 30%;
    max-width: 50;
    min-width: 30;
    border-left: solid $primary 1;
    height: 100%;
    layout: vertical;
}

#status-bar {
    dock: bottom;
    height: 1;
    background: $surface-lighten-1;
}

/* Collapsed sidebars */
#left-sidebar.collapsed {
    width: 0;
    min-width: 0;
    border-right: none;
}

#right-sidebar.collapsed {
    width: 0;
    min-width: 0;
    border-left: none;
}

/* Tab Styling */
TabbedContent TabBar {
    background: $surface-darken-1;
    height: 1;
}

TabbedContent TabButton {
    padding: 0 2;
    margin: 0 1;
    min-width: 15;
    max-width: 30;
}

TabbedContent TabButton.-active {
    background: $primary;
    color: $text;
    text-style: bold;
}

TabbedContent TabButton.dirty::after {
    content: "●";
    color: $warning;
    margin-left: 1;
}

/* Tree Styling */
Tree {
    background: transparent;
}

Tree .tree--cursor {
    background: $primary 20%;
}

Tree .tree--cursor-line {
    color: $text;
}

/* Modal Overlay */
.modal-overlay {
    layer: modal;
    align: center middle;
    background: $surface 95%;
}

.modal-dialog {
    width: 80%;
    max-width: 100;
    height: auto;
    max-height: 80%;
    background: $surface;
    border: solid $primary 1;
    padding: 2;
}

/* Syntax Highlighting (for payload editor) */
.json-key { color: $accent; }
.json-string { color: $success; }
.json-number { color: $warning; }
.json-boolean { color: $error; }
.json-null { color: $text-muted; }
```

---

## 11. Event Flow

### 11.1 Startup
```
mycode CLI entry
    ▼
MyCodeApp.run()
    ▼
on_mount()
    ▼
load_workspace_state() → restore tabs, sidebars
    ▼
if no providers.json:
    push_screen(SetupWizard())
    ▼
SetupWizard completes → save providers.json, .env
    ▼
pop_screen() → Main TUI ready
```

### 11.2 New Work History
```
User: Ctrl+N (in project) or "New Work History"
    ▼
Create SQLite session
    ▼
Create WorkHistory entry in workspaces.json
    ▼
Add to ProjectTree
    ▼
Create TabPane in CenterTabs
    ▼
Activate new tab
    ▼
Set agent CWD to project folder
```

### 11.3 Tab Switch
```
User: Ctrl+Tab / Click tab
    ▼
TabbedContent.TabActivated event
    ▼
CenterTabs.on_tab_activated()
    ▼
Get tab's project_id
    ▼
Set agent.cwd = project.trusted_folder
    ▼
Update RightSidebar FolderTree path
    ▼
Update StatusBar project name
```

### 11.4 Trust Folder
```
User: "Add Project Folder" → select path
    ▼
Check trusted_folders.json
    ▼
If not trusted: push_screen(TrustDialog(path))
    ▼
User: "Allow & Trust" + "Remember"
    ▼
Write to trusted_folders.json
    ▼
Add project to workspaces.json
    ▼
Refresh ProjectTree
    ▼
Start Watchdog + RAG indexing
```

### 11.5 Send Message
```
User: Type in InputArea → Ctrl+Enter
    ▼
InputArea.Submitted event
    ▼
ChatWorkspace.on_input_submitted()
    ▼
Append user message to MessageList
    ▼
Call agent.run(user_input, cwd=tab.project_cwd)
    ▼
Stream: reasoning → content → tool calls
    ▼
Display tool calls in ToolCallView
    ▼
On tool results: append to MessageList
    ▼
On final: save to cache, update SQLite
    ▼
Mark tab dirty=False
```

---

## 12. Implementation Phases

### Phase 5A: Foundation & Setup Wizard (Week 1-2)
- [ ] `providers.json`, `workspaces.json`, `trusted_folders.json`, `config.toml` data models
- [ ] Persistence layer (load/save/migrate)
- [ ] Setup Wizard modal (5 steps, validation, model fetching)
- [ ] Provider profile management (add/switch/delete)
- [ ] Integration with existing agent (use active profile)

### Phase 5B: Left Sidebar (Week 2-3)
- [ ] ProjectTree widget with Tree view
- [ ] Project node + Work History nodes
- [ ] Ad-hoc section
- [ ] Inline rename (F2)
- [ ] Context menus (new, delete, rename)
- [ ] "Add Project Folder" → folder picker → trust dialog
- [ ] Trust folder dialog + persistence

### Phase 5C: Center Tabs (Week 3-4)
- [ ] TabbedContent subclass with custom tab bar
- [ ] ChatWorkspace per tab (MessageList, ToolCallView, InputArea)
- [ ] Tab context awareness (CWD per project)
- [ ] Tab management: new, close, split, duplicate, rename, reorder
- [ ] Keyboard shortcuts (Ctrl+T/W/Tab/Shift+Tab)
- [ ] Tab state persistence + restoration

### Phase 5D: Right Sidebar (Week 4-5)
- [ ] FolderManager widget
- [ ] FolderTree with tree-sitter awareness (icons per file type)
- [ ] Context menu (Open, Read, Edit, Delete, Copy Path, Add to Context, Run Tests, Search)
- [ ] Per-project folder view (switches with tab)
- [ ] Refresh button, Trust Settings button

### Phase 5E: Polish & Integration (Week 5-6)
- [ ] Command Palette (Ctrl+Shift+P)
- [ ] Cross-History Search (Ctrl+Shift+F)
- [ ] Raw Payload Editor with syntax highlighting
- [ ] Provider Settings re-accessible via palette
- [ ] Extended keybindings (all shortcuts)
- [ ] Theme system integration
- [ ] Animations (sidebar collapse, tab transitions)
- [ ] Full test coverage
- [ ] Documentation updates

---

## 13. Testing Checklist

### Unit Tests
- [ ] Data model serialization/deserialization
- [ ] Persistence load/save/migrate
- [ ] Setup Wizard step validation
- [ ] Provider model fetching (mocked)
- [ ] Payload JSON validation

### Widget Tests
- [ ] ProjectTree: add project, add history, rename, delete
- [ ] CenterTabs: add/close/switch/split/duplicate tabs
- [ ] ChatWorkspace: message display, tool streaming, input
- [ ] FolderManager: tree navigation, context menu actions
- [ ] SetupWizard: all 5 steps, validation, persistence
- [ ] TrustDialog: allow/deny, remember checkbox

### Integration Tests
- [ ] Full startup → wizard → main TUI
- [ ] Create project → trust folder → create history → open tab → send message
- [ ] Multi-tab: switch tabs → CWD changes → tools run in correct folder
- [ ] Persistence: restart → tabs restored → project/history intact
- [ ] Provider switch: change profile → new chats use new model
- [ ] Sidebar toggle: F1/F2 → collapse/expand → state saved

### E2E Tests
- [ ] Complete workflow: setup → project → code task → verify file changes
- [ ] Multi-project: switch projects → contexts isolated
- [ ] Ad-hoc work: no project → history saved → can assign to project later
- [ ] Trust flow: deny → no access; allow → full access

---

## 14. Migration from v1 TUI

### Breaking Changes
- `app.py` completely rewritten (new layout)
- `SessionTree` → `ProjectTree` (different data model)
- `FileTree` → `FolderManager` (per-project, with trust)
- Single chat → Tabbed workspaces
- Session management → Work History management

### Migration Strategy
- Keep v1 TUI as `mycode --legacy-tui` for transition period
- Auto-migrate `history.db` sessions → `workspaces.json` histories
- Show migration notice on first v2 launch
- v1 config (`.env`) compatible, just add `providers.json`

---

## 15. Future Extensions (Post-Phase 5)

- **Split Panes:** Horizontal/vertical splits within tab
- **Git Integration:** Branch indicator, status in tab bar
- **Debug Console:** REPL panel for running code
- **Terminal Tabs:** Embedded terminal per project
- **Remote Workspaces:** SSH-connected project folders
- **Collaborative Editing:** Multi-user session sharing
- **AI Agent Tabs:** Subagent tabs for parallel tasks

---

## 16. Phase 4 Multi-Surface Integration

### 16.1 Shared Persistence Layer
All MyCode surfaces (TUI, Web, Desktop, IDE extensions) share the **same local persistence files**:

```
~/.mycode/
├── providers.json          # LLM profiles — shared across ALL surfaces
├── workspaces.json         # Projects, histories, tabs — shared
├── trusted_folders.json    # Folder acknowledgments — shared
├── config.toml             # UI preferences — surface-specific sections
├── history.db              # SQLite sessions — shared
├── chroma_data/            # Semantic cache — shared
└── rag_data/               # Codebase index — shared
```

**Implications:**
- Provider configured in TUI → immediately available in Web/Desktop/IDE
- Project added in VS Code extension → appears in TUI left sidebar
- Trust granted in Web UI → respected by terminal tools
- Tab state (`workspaces.json`) can sync across surfaces

### 16.2 Surface-Specific Config Sections
```toml
# ~/.mycode/config.toml
[ui.tui]
theme = "dark"
font_size = 14
left_sidebar_open = true

[ui.web]
theme = "light"
compact_mode = false

[ui.desktop]
window_width = 1400
window_height = 900

[ui.vscode]
auto_focus_chat = true
```

### 16.3 Real-Time Sync (Optional)
For live collaboration across surfaces:
- **File watcher** on `~/.mycode/` → broadcast changes via WebSocket
- **WebSocket server** (Phase 4) → push updates to connected surfaces
- **Conflict resolution:** Last-write-wins for JSON; SQLite handles concurrent reads

### 16.4 Remote Control Integration (Phase 4)
- **TUI as host:** Running TUI session exposes WebSocket endpoint
- **Mobile/Web as client:** Connect to TUI → view/control session
- **Session teleport:** Move active tab context between surfaces
- **Shared state:** `workspaces.json` `active_tab_id` synced in real-time

### 16.5 IDE Extension Integration (Phase 4)
- **VS Code / JetBrains:** Read `providers.json` for model config
- **Project sync:** IDE workspace folders ↔ MyCode trusted folders
- **Tab context:** IDE editor focus → auto-switch TUI tab (if linked)
- **Tool execution:** IDE can trigger MyCode tools via CLI or local API

### 16.6 Desktop App (Tauri/Electron) — Phase 4A
- **Wrapper around TUI:** Embed Textual via `textual-web` or PTY
- **Native menus:** File → New Project, View → Toggle Sidebars
- **System tray:** Background agent with notifications
- **Auto-update:** Check GitHub releases on startup

### 16.7 Web Interface — Phase 4A
```
┌─────────────────────────────────────────────────────────────┐
│  React Frontend (Port 3000)                                 │
│  ┌─────────────┐  ┌────────────────┐  ┌─────────────────┐  │
│  │ Left:       │  │ Center:        │  │ Right:          │  │
│  │ Projects    │  │ Tabbed Chat    │  │ Folder Tree     │  │
│  │ (TreeView)  │  │ (MessageList)  │  │ (FileExplorer)  │  │
│  └─────────────┘  └────────────────┘  └─────────────────┘  │
└─────────────────────────────────────────────────────────────┘
         │                    │                    │
         ▼                    ▼                    ▼
┌─────────────────────────────────────────────────────────────┐
│  FastAPI + WebSocket Backend (Port 8000)                    │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────┐     │
│  │ Session     │  │ Tool        │  │ File Watcher    │     │
│  │ Manager     │  │ Executor    │  │ (Watchdog)      │     │
│  └─────────────┘  └─────────────┘  └─────────────────┘     │
│         │                    │                    │          │
│         └────────────────────┼────────────────────┘          │
│                              ▼                               │
│                    SHARED CORE (Python)                       │
└─────────────────────────────────────────────────────────────┘
```
- **Same UI layout** as TUI (left/center/right) but in browser
- **WebSocket** for real-time streaming (reasoning, tools, messages)
- **Authentication:** Local token in `~/.mycode/web_auth.json`

### 16.8 Data Model Compatibility
All surfaces use **identical JSON schemas**:

```python
# providers.json — identical
ProviderProfile: {id, name, api_key, base_url, model, raw_payload, is_default, created_at}

# workspaces.json — identical  
WorkspaceState: {projects[], ad_hoc_histories[], tab_state{}, ui_preferences{}}

# trusted_folders.json — identical
TrustedFolder: {path, project_id, acknowledged_at, permissions[]}
```

**Version field** in each file enables migration across surface updates.

---

*End of TUI Specification v2.0*