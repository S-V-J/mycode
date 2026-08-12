# Phase 4: Multi-Surface & Enterprise 📋 **PLANNED**

**Goal:** Run on multiple platforms with enterprise features

## Target Features (68 atomic items from 217 total)

### Platforms & Surfaces (10)
| # | Platform | Description | MyCode Implementation |
|---|----------|-------------|----------------------|
| 1 | VS Code Extension | Full IDE integration | TypeScript extension + Python backend |
| 2 | JetBrains Plugin | IntelliJ/PyCharm/WebStorm | Kotlin plugin + Python backend |
| 3 | Desktop (macOS) | Native app with preview | Tauri/Electron + Python backend |
| 4 | Desktop (Windows) | Native app | Tauri/Electron + Python backend |
| 5 | Desktop (Linux) | Native AppImage | Tauri/Electron + Python backend |
| 6 | Desktop (WSL) | Windows Subsystem Linux | Current TUI + Windows integration |
| 7 | Web Interface | Cloud environments in browser | React frontend + WebSocket backend |
| 8 | Mobile App | iOS/Android with push | React Native + WebSocket backend |
| 9 | Chrome Extension | Browser automation | Manifest V3 + content scripts |
| 10 | Slack Integration | Bot in Slack channels | Slack Bolt + session management |

### Model Provider Backends (5)
| # | Provider | Description | MyCode Implementation |
|---|----------|-------------|----------------------|
| 1 | Anthropic API | Direct Claude access | Already via OpenAI-compatible |
| 2 | Amazon Bedrock | AWS managed models | `boto3` + Bedrock runtime |
| 3 | Google Vertex AI | GCP Agent Platform | `google-cloud-aiplatform` |
| 4 | Microsoft Foundry | Azure AI Foundry | `azure-ai-inference` |
| 5 | Claude Platform on AWS | Anthropic's AWS offering | Bedrock + custom endpoint |

### LLM Gateway Types (2)
| # | Gateway | Description |
|---|---------|-------------|
| 1 | Claude Apps Gateway | Anthropic's managed gateway |
| 2 | Third-party/Custom | Self-hosted gateway support |

### Sandboxing & Isolation (5)
| # | Approach | Description | MyCode Implementation |
|---|----------|-------------|----------------------|
| 1 | Sandboxed Bash Tool | Current subprocess with limits | ✅ Implemented (Phase 1) |
| 2 | Sandbox Runtime | Dedicated isolated runtime | `gVisor` / `firecracker` |
| 3 | Dev Containers | VS Code devcontainer support | `.devcontainer.json` + Docker |
| 4 | Custom Containers | User-defined Docker images | `docker run` with profiles |
| 5 | Virtual Machines | Full VM isolation | `libvirt` / `qemu` / `multipass` |

### Subagents & Agent Teams (5)
| # | Feature | Description |
|---|---------|-------------|
| 1 | Named subagents | Explore (codebase research), Plan (architecture) |
| 2 | Custom subagents | User-defined with tool restrictions |
| 3 | Agent teams | Multiple agents collaborating |
| 4 | Cross-session messaging | Sessions communicate |
| 5 | Worktrees for isolation | Git worktrees per agent/session |

### Self-Hosted & Enterprise (15)
| # | Feature | Description |
|---|---------|-------------|
| 1 | Runner orchestration | Kubernetes/Docker Compose deployment |
| 2 | Admin console | Org settings, user management |
| 3 | Managed settings | Policy delivery to clients |
| 4 | Auto-mode config | Classifier boundaries, allow/block rules |
| 5 | Corporate launcher | Enforced wrapper executable |
| 6 | DevContainers | Standardized dev environments |
| 7 | Network config | Proxy, mTLS, custom CA certs |
| 8 | GitHub Enterprise Server | GHES integration |
| 9 | GitLab CI/CD | Native GitLab integration |
| 10 | Amazon Bedrock | AWS integration |
| 11 | Google Vertex AI | GCP integration |
| 12 | Microsoft Foundry | Azure integration |
| 13 | Audit logging | Compliance trail |
| 14 | SSO/SAML/OIDC | Enterprise auth |
| 15 | Spend limits | Cost controls per org/user |

### Remote Control & Access (3)
| # | Feature | Description |
|---|---------|-------------|
| 1 | Remote Control | Mobile/web control of terminal sessions |
| 2 | Trusted Devices | Device enrollment for org |
| 3 | Teleport | Move sessions between surfaces |

### Git & CI/CD Integration (8)
| # | Feature | Description |
|---|---------|-------------|
| 1 | GitHub Actions | `@claude` mentions, skills |
| 2 | GitHub Enterprise Server | Self-hosted GitHub |
| 3 | GitLab CI/CD | Native GitLab integration |
| 4 | Worktrees | Git worktrees for parallel tasks |
| 5 | Branch isolation | Per-agent worktrees |
| 6 | PR automation | Auto-fix, review, merge |
| 7 | Security scanning | Plugin-based security review |
| 8 | Code review | `/code-review` with custom rules |

### Core Tools for Phase 4 (2/15)
- ❌ **PowerShell** - Windows PowerShell support → **Phase 4**
- ❌ **Agent** - Subagent spawning → **Phase 4**

---

## Implementation Priority

### Phase 4A: Desktop & Web (Core)
1. Tauri/Electron wrapper for current TUI
2. WebSocket backend for real-time communication
3. React frontend for web interface
4. Mobile app (React Native)

### Phase 4B: IDE Integrations
1. VS Code extension (TypeScript)
2. JetBrains plugin (Kotlin)

### Phase 4C: Enterprise & Cloud
1. MCP server management
2. Runner orchestration (K8s)
3. Admin console
4. SSO/OIDC integration
5. Audit logging

### Phase 4D: Advanced Platforms
1. Chrome extension
2. Slack bot
3. Computer use (screen control)
4. Remote Control

---

## File Structure (Planned)
```
src/mycode/
├── desktop/
│   ├── tauri/              # Tauri config
│   ├── electron/           # Electron fallback
│   └── python/             # Python backend bridge
├── web/
│   ├── frontend/           # React app
│   ├── backend/            # FastAPI + WebSocket
│   └── mobile/             # React Native
├── ide/
│   ├── vscode/             # VS Code extension
│   └── jetbrains/          # JetBrains plugin
├── chrome/
│   └── extension/          # Chrome extension
├── enterprise/
│   ├── admin.py            # Admin console
│   ├── runner.py           # Runner orchestration
│   ├── sso.py              # SSO integration
│   └── audit.py            # Audit logging
└── remote/
    ├── control.py          # Remote Control
    └── teleport.py         # Session teleport
```

---

## Dependencies
- `tauri` / `electron` for desktop
- `fastapi` + `websockets` for web backend
- `react` + `react-native` for frontend/mobile
- `kubernetes` client for runner orchestration
- `authlib` for SSO/OIDC
- `playwright` / `pyautogui` for computer use

---

## Verification Checklist
- [ ] Desktop app launches TUI in native window
- [ ] Web interface connects to local agent via WebSocket
- [ ] VS Code extension activates and communicates
- [ ] All 5 model providers connect and work
- [ ] Dev containers launch with MyCode
- [ ] Subagents spawn and collaborate
- [ ] Admin console manages org settings
- [ ] Audit logs capture all actions
- [ ] SSO login works
- [ ] Spend limits enforce correctly