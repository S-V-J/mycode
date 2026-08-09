import typer
from rich.console import Console
from rich.panel import Panel
from .config import ensure_config
from .llm_client import NemotronClient
from .agent import Agent

app = typer.Typer(help="MyCode: Open-Source Agentic CLI")
console = Console()

@app.command()
def main():
    """Start the MyCode interactive CLI session."""
    console.print(Panel.fit(
        "[bold green]MyCode v0.2.0 (Agentic)[/bold green]\n"
        "[dim]Open-Source Agentic CLI | Powered by NVIDIA Nemotron[/dim]",
        border_style="blue"
    ))
    
    api_key = ensure_config()
    client = NemotronClient(api_key)
    agent = Agent(client)
    
    console.print("\n[bold cyan]Ready.[/bold cyan] Type your request or [yellow]/exit[/yellow] to quit.\n")
    
    while True:
        try:
            user_input = console.input("[bold green]❯[/bold green] ")
            
            cmd = user_input.strip().lower()
            if cmd == "/exit":
                console.print("[yellow]Goodbye![/yellow]")
                break
            if not user_input.strip():
                continue
                
            agent.run(user_input)
                
        except KeyboardInterrupt:
            console.print("\n[yellow]Interrupted. Type /exit to quit.[/yellow]")
            continue
        except Exception as e:
            console.print(f"\n[bold red]Fatal Error:[/bold red] {e}")
            break

if __name__ == "__main__":
    app()
