"""Configuration management for MyCode."""
import os
import stat
import tomllib
try:
    import tomli_w
except ImportError:
    import json
    tomli_w = None
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional

MYCODE_DIR = Path.home() / ".mycode"
MYCODE_DIR.mkdir(exist_ok=True, mode=0o700)
CONFIG_FILE = MYCODE_DIR / "config.toml"
ENV_FILE = MYCODE_DIR / ".env"


@dataclass
class UIConfig:
    """UI preferences."""
    theme: str = "dark"
    font_size: int = 14
    animations: bool = True
    left_sidebar_open: bool = True
    right_sidebar_open: bool = True


@dataclass
class KeybindingsConfig:
    """Keybinding overrides."""
    custom: dict = field(default_factory=dict)


@dataclass
class ProviderConfig:
    """Provider preferences."""
    auto_fetch_models: bool = True
    default_temperature: float = 0.2
    default_max_tokens: int = 4096


@dataclass
class MyCodeConfig:
    """Complete configuration."""
    ui: UIConfig = field(default_factory=UIConfig)
    keybindings: KeybindingsConfig = field(default_factory=KeybindingsConfig)
    provider: ProviderConfig = field(default_factory=ProviderConfig)


def load_config() -> MyCodeConfig:
    """Load configuration from config.toml."""
    if not CONFIG_FILE.exists():
        return MyCodeConfig()

    try:
        data = tomllib.loads(CONFIG_FILE.read_text())
        ui_data = data.get("ui", {})
        kb_data = data.get("keybindings", {})
        prov_data = data.get("provider", {})

        return MyCodeConfig(
            ui=UIConfig(**ui_data),
            keybindings=KeybindingsConfig(custom=kb_data.get("custom", {})),
            provider=ProviderConfig(**prov_data),
        )
    except Exception:
        return MyCodeConfig()


def save_config(config: MyCodeConfig):
    """Save configuration to config.toml."""
    data = {
        "ui": {
            "theme": config.ui.theme,
            "font_size": config.ui.font_size,
            "animations": config.ui.animations,
            "left_sidebar_open": config.ui.left_sidebar_open,
            "right_sidebar_open": config.ui.right_sidebar_open,
        },
        "keybindings": {
            "custom": config.keybindings.custom,
        },
        "provider": {
            "auto_fetch_models": config.provider.auto_fetch_models,
            "default_temperature": config.provider.default_temperature,
            "default_max_tokens": config.provider.default_max_tokens,
        },
    }
    if tomli_w:
        CONFIG_FILE.write_text(tomli_w.dumps(data))
    else:
        # Fallback: write as JSON-compatible TOML
        import json
        CONFIG_FILE.write_text(json.dumps(data, indent=2))


def ensure_config() -> str:
    """Ensure config directory and .env exist, prompt for API key if missing."""
    MYCODE_DIR.mkdir(parents=True, exist_ok=True)
    if not ENV_FILE.exists():
        ENV_FILE.touch()
        os.chmod(ENV_FILE, stat.S_IRUSR | stat.S_IWUSR)

    from dotenv import load_dotenv
    load_dotenv(ENV_FILE)
    api_key = os.getenv("NVIDIA_API_KEY", "")

    if not api_key:
        from rich.console import Console
        from rich.prompt import Prompt
        console = Console()
        console.print("\n[bold yellow]⚠ NVIDIA API Key not found.[/bold yellow]")
        console.print("Please generate a key at https://build.nvidia.com/ and paste it below.")
        console.print("[dim]Your key will be saved securely to ~/.mycode/.env with 0600 permissions.[/dim]\n")
        api_key = Prompt.ask("[bold cyan]Paste your NVIDIA API Key[/bold cyan]")
        from dotenv import set_key
        set_key(ENV_FILE, "NVIDIA_API_KEY", api_key)
        console.print(f"\n[bold green]✓ API Key securely saved to {ENV_FILE}[/bold green]\n")

    return api_key


def save_api_key(api_key: str):
    """Save API key to .env file."""
    ENV_FILE.parent.mkdir(parents=True, exist_ok=True)
    if not ENV_FILE.exists():
        ENV_FILE.touch()
    os.chmod(ENV_FILE, stat.S_IRUSR | stat.S_IWUSR)
    from dotenv import set_key
    set_key(ENV_FILE, "NVIDIA_API_KEY", api_key)


def find_mycode_md(start_path: Path) -> str:
    """Traverses up the directory tree to find MYCODE.md."""
    from rich.console import Console
    console = Console()
    current_dir = start_path.resolve()
    while current_dir != current_dir.parent:
        target_file = current_dir / "MYCODE.md"
        if target_file.exists():
            try:
                console.print(f"[dim]📖 Loaded project rules from {target_file}[/dim]")
                return target_file.read_text(encoding="utf-8")
            except Exception:
                pass
        current_dir = current_dir.parent
    return ""


# Global config instance
config = load_config()
