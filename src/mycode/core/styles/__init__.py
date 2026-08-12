"""Style system for MyCode."""
from .themes import ThemeManager, Theme, BUILTIN_THEMES, theme_manager
from .output import OutputStyle, StyleConfig, STYLE_DESCRIPTIONS

__all__ = [
    "ThemeManager", "Theme", "BUILTIN_THEMES", "theme_manager",
    "OutputStyle", "StyleConfig", "STYLE_DESCRIPTIONS",
]
