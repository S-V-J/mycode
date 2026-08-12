"""Theme system for MyCode TUI."""
from dataclasses import dataclass, field
from typing import Dict, List, Optional
import json
import os
from pathlib import Path

MYCODE_DIR = Path.home() / ".mycode"
THEMES_DIR = MYCODE_DIR / "themes"
THEMES_DIR.mkdir(exist_ok=True)


@dataclass
class Theme:
    """TUI theme definition."""
    name: str
    background: str = "#1a1a2e"
    surface: str = "#16213e"
    primary: str = "#0f3460"
    secondary: str = "#533483"
    accent: str = "#e94560"
    text: str = "#eee"
    text_muted: str = "#888"
    success: str = "#4ade80"
    warning: str = "#fbbf24"
    error: str = "#f87171"
    border: str = "#333"

    def to_css_vars(self) -> str:
        return "\n".join(
            f"${k}: {v};"
            for k, v in [
                ("background", self.background),
                ("surface", self.surface),
                ("primary", self.primary),
                ("secondary", self.secondary),
                ("accent", self.accent),
                ("text", self.text),
                ("text-muted", self.text_muted),
                ("success", self.success),
                ("warning", self.warning),
                ("error", self.error),
                ("border", self.border),
            ]
        )

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "background": self.background,
            "surface": self.surface,
            "primary": self.primary,
            "secondary": self.secondary,
            "accent": self.accent,
            "text": self.text,
            "text-muted": self.text_muted,
            "success": self.success,
            "warning": self.warning,
            "error": self.error,
            "border": self.border,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Theme":
        return cls(**data)


BUILTIN_THEMES = {
    "dark": Theme(
        name="dark",
        background="#1a1a2e",
        surface="#16213e",
        primary="#0f3460",
        secondary="#533483",
        accent="#e94560",
        text="#eee",
        text_muted="#888",
        success="#4ade80",
        warning="#fbbf24",
        error="#f87171",
        border="#333",
    ),
    "light": Theme(
        name="light",
        background="#f8fafc",
        surface="#ffffff",
        primary="#3b82f6",
        secondary="#8b5cf6",
        accent="#ef4444",
        text="#1e293b",
        text_muted="#64748b",
        success="#22c55e",
        warning="#eab308",
        error="#dc2626",
        border="#e2e8f0",
    ),
    "monokai": Theme(
        name="monokai",
        background="#272822",
        surface="#1e1f1c",
        primary="#f92672",
        secondary="#66d9ef",
        accent="#a6e22e",
        text="#f8f8f2",
        text_muted="#75715e",
        success="#a6e22e",
        warning="#e6db74",
        error="#f92672",
        border="#3e3d32",
    ),
    "nord": Theme(
        name="nord",
        background="#2e3440",
        surface="#3b4252",
        primary="#88c0d0",
        secondary="#81a1c1",
        accent="#5e81ac",
        text="#eceff4",
        text_muted="#d8dee9",
        success="#a3be8c",
        warning="#ebcb8b",
        error="#bf616a",
        border="#4c566a",
    ),
}


class ThemeManager:
    """Manage themes."""

    def __init__(self):
        self.current_theme: Theme = BUILTIN_THEMES["dark"]
        self._load_custom_themes()

    def _load_custom_themes(self):
        """Load custom themes from disk."""
        if THEMES_DIR.exists():
            for theme_file in THEMES_DIR.glob("*.json"):
                try:
                    data = json.loads(theme_file.read_text())
                    theme = Theme.from_dict(data)
                    BUILTIN_THEMES[theme.name] = theme
                except Exception:
                    pass

    def set_theme(self, name: str) -> bool:
        if name in BUILTIN_THEMES:
            self.current_theme = BUILTIN_THEMES[name]
            self._save_preference(name)
            return True
        return False

    def get_theme_names(self) -> List[str]:
        return list(BUILTIN_THEMES.keys())

    def get_current_theme(self) -> Theme:
        return self.current_theme

    def _save_preference(self, name: str):
        """Save theme preference to config.toml."""
        config_file = MYCODE_DIR / "config.toml"
        try:
            content = config_file.read_text() if config_file.exists() else ""
            import re
            if re.search(r'theme\s*=\s*".*?"', content):
                content = re.sub(r'theme\s*=\s*".*?"', f'theme = "{name}"', content)
            else:
                content += f'\n[ui]\ntheme = "{name}"\n'
            config_file.write_text(content)
        except Exception:
            pass

    def create_custom_theme(self, name: str, theme: Theme) -> bool:
        BUILTIN_THEMES[name] = theme
        theme_file = THEMES_DIR / f"{name}.json"
        try:
            theme_file.write_text(json.dumps(theme.to_dict(), indent=2))
            return True
        except Exception:
            return False


# Global instance
theme_manager = ThemeManager()
