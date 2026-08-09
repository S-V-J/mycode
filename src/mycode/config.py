import os
import stat
from pathlib import Path
from dotenv import load_dotenv, set_key
from rich.console import Console
from rich.prompt import Prompt

console = Console()

# Define the secure vault location
MYCODE_DIR = Path.home() / ".mycode"
ENV_FILE = MYCODE_DIR / ".env"

def ensure_config() -> str:
    """Ensures the config directory and .env file exist, and prompts for API key if missing."""
    MYCODE_DIR.mkdir(parents=True, exist_ok=True)
    
    if not ENV_FILE.exists():
        ENV_FILE.touch()
        # Set strict POSIX permissions (read/write for owner only: 0600)
        os.chmod(ENV_FILE, stat.S_IRUSR | stat.S_IWUSR)

    # Load existing environment variables from the vault
    load_dotenv(ENV_FILE)
    api_key = os.getenv("NVIDIA_API_KEY")
    
    if not api_key:
        console.print("\n[bold yellow]⚠ NVIDIA API Key not found.[/bold yellow]")
        console.print("Please generate a key at [link=https://build.nvidia.com/]https://build.nvidia.com/[/link] and paste it below.")
        console.print("[dim]Your key will be saved securely to ~/.mycode/.env with 0600 permissions.[/dim]\n")
        
        api_key = Prompt.ask("[bold cyan]Paste your NVIDIA API Key[/bold cyan]")
        
        # Save to the secure vault
        set_key(ENV_FILE, "NVIDIA_API_KEY", api_key)
        console.print(f"\n[bold green]✓ API Key securely saved to {ENV_FILE}[/bold green]\n")
        
    return api_key
