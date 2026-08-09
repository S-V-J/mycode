import typer
from rich.console import Console
from rich.panel import Panel
from .config import ensure_config
from .llm_client import NemotronClient

app = typer.Typer(help="MyCode: Open-Source Agentic CLI")
console = Console()

@app.command()
def main():
    """Start the MyCode interactive CLI session."""
    console.print(Panel.fit(
        "[bold green]MyCode v0.1.0[/bold green]\n"
        "[dim]Open-Source Agentic CLI | Powered by NVIDIA Nemotron[/dim]",
        border_style="blue"
    ))
    
    # 1. Secure Configuration & API Key Retrieval
    api_key = ensure_config()
    
    # 2. Initialize LLM Client
    client = NemotronClient(api_key)
    
    # 3. Interactive Agentic Loop (Phase 1: Basic Chat)
    messages = [
        {"role": "system", "content": "You are MyCode, an elite autonomous coding assistant. Think step-by-step."}
    ]
    
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
                
            messages.append({"role": "user", "content": user_input})
            
            console.print() # Spacing before response
            response = client.stream_chat(messages)
            
            if response:
                messages.append({"role": "assistant", "content": response})
                
        except KeyboardInterrupt:
            console.print("\n[yellow]Interrupted. Type /exit to quit.[/yellow]")
            continue
        except Exception as e:
            console.print(f"\n[bold red]Fatal Error:[/bold red] {e}")
            break

if __name__ == "__main__":
    app()
