# Phase 5: Advanced Intelligence & Polish 📋 **PLANNED**

**Goal:** Intelligence features and developer experience

## Target Features (22 atomic items from 217 total)

### Intelligence Features (8)
| # | Feature | Description | MyCode Implementation |
|---|---------|-------------|----------------------|
| 1 | Prompt Library | Curated templates for common tasks | `.mycode/prompts/` + `/prompt` command |
| 2 | Output Styles | Custom formatting (JSON, YAML, table, etc.) | `OutputStyle` class + `--style` flag |
| 3 | Advisor Model | Secondary model reviews primary | Dual-model architecture (Phase 3 MCP) |
| 4 | Fast Mode | Cheaper model for simple tasks | Model routing based on complexity |
| 5 | UltraReview | Automated PR review | GitHub Action + review skill |
| 6 | Routines | Scheduled/triggered workflows | Cron + event triggers (Phase 2) |
| 7 | Context Window Management | Auto-compact, token budgeting | Token counter + compaction strategy |
| 8 | Prompt Caching (Advanced) | Prefix caching, TTL control | Enhanced semantic cache with prefixes |

### Developer Experience (7)
| # | Feature | Description | MyCode Implementation |
|---|---------|-------------|----------------------|
| 1 | Keybindings | Vim mode, custom shortcuts | Textual keybinding config + Vim mode |
| 2 | Accessibility | Screen reader support | Textual accessibility + ARIA |
| 3 | Voice Dictation | Speech-to-text input | `whisper.cpp` / `speech_recognition` |
| 4 | Debug Config Inspection | See loaded config, context | `/debug` command + TUI panel |
| 5 | Analytics/Usage Monitoring | OTLP metrics, cost tracking | `opentelemetry` + local Prometheus |
| 6 | Cost Tracking | Token usage, estimated costs | Per-session + per-project totals |
| 7 | Glossary Completion | Terminology definitions | Built-in glossary from docs |

### Polish & UX (7)
| # | Feature | Description | MyCode Implementation |
|---|---------|-------------|----------------------|
| 1 | Theme System | Custom TUI color schemes | CSS variables + theme files |
| 2 | Animations | Smooth transitions | Textual animations |
| 3 | Diff Algorithm | Better diff rendering | `difflib` + semantic diff |
| 4 | Search | Fuzzy search in chat/files | `fzf`-style search in TUI |
| 5 | Multi-cursor | Edit multiple lines | TextArea multi-cursor |
| 6 | Snippets | Code snippet expansion | Tab-triggered snippets |
| 7 | Session Export | Export chat as MD/JSON/HTML | `/export` command |

---

## Implementation Plan

### File Structure
```
src/mycode/core/
├── prompts/
│   ├── __init__.py
│   ├── library.py          # Prompt templates
│   └── registry.py         # User prompts
├── styles/
│   ├── __init__.py
│   ├── output.py           # Output formatters
│   └── themes.py           # TUI themes
├── advisor/
│   ├── __init__.py
│   ├── reviewer.py         # Code review logic
│   └── fast_mode.py        # Model routing
├── analytics/
│   ├── __init__.py
│   ├── metrics.py          # OTLP metrics
│   ├── costs.py            # Token/cost tracking
│   └── exporter.py         # Prometheus/Grafana
├── accessibility/
│   ├── __init__.py
│   ├── screen_reader.py    # Textual a11y
│   └── voice.py            # Voice input
├── glossary/
│   ├── __init__.py
│   └── terms.py            # Built-in glossary
└── debug/
    ├── __init__.py
    └── inspector.py        # Config/context inspector
```

### Configuration
- `.mycode/themes/` - User themes
- `.mycode/prompts/` - User prompt templates
- `.mycode/snippets/` - Code snippets
- `~/.mycode/config.toml` - Global settings (theme, keys, etc.)

### Dependencies
- `opentelemetry-api` + `opentelemetry-sdk` for metrics
- `prometheus-client` for local metrics
- `speech_recognition` + `whisper.cpp` for voice
- `pygments` for syntax highlighting in diffs
- `fuzzywuzzy` for search
- `textual[dev]` for development tools

---

## Verification Checklist
- [ ] Prompt library loads and executes templates
- [ ] Output styles format correctly (JSON, table, etc.)
- [ ] Advisor model reviews and suggests improvements
- [ ] Fast mode routes to cheaper model
- [ ] UltraReview runs on PRs via GitHub Action
- [ ] Context auto-compacts at token limit
- [ ] Vim mode works in TextArea
- [ ] Screen reader announces correctly
- [ ] Voice input transcribes accurately
- [ ] `/debug` shows config + context
- [ ] Metrics export to Prometheus
- [ ] Cost tracking accurate per session
- [ ] Glossary search works
- [ ] Theme switching works live
- [ ] Session export produces valid files