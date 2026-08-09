import subprocess
from rich.console import Console
from rich.prompt import Confirm

console = Console()

# Safety interceptor: Block highly destructive commands without explicit user approval
DANGEROUS_KEYWORDS = ["rm -rf", "sudo", "chmod 777", "mkfs", "dd if=", ":(){:|:&};:", ">/dev/sda"]

def execute_bash(command: str) -> str:
    """Executes a bash command securely with timeout and safety checks."""
    if any(keyword in command for keyword in DANGEROUS_KEYWORDS):
        console.print(f"\n[bold red]⚠ Safety Alert:[/bold red] Destructive command detected: [yellow]{command}[/yellow]")
        if not Confirm.ask("[bold red]Allow execution?[/bold red]"):
            return "Command blocked by user."
            
    try:
        # Run in shell, capture stdout/stderr, enforce 30s timeout
        result = subprocess.run(
            command, shell=True, capture_output=True, text=True, timeout=30, cwd="."
        )
        output = result.stdout + result.stderr
        if not output.strip():
            return "Command executed successfully (no output)."
        return output
    except subprocess.TimeoutExpired:
        return "Error: Command timed out after 30 seconds."
    except Exception as e:
        return f"Error executing command: {str(e)}"
