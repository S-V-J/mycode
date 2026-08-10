import typer
from pathlib import Path
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from .core.config import ensure_config
from .core.llm_client import NemotronClient
from .core.agent import Agent
from .core.rag import index_directory, start_watcher
from .core.hooks import (
    get_hook_registry, fire_hook_sync, HookEvent, HookConfig, HookHandlerType
)
from .core.scheduler import (
    get_scheduler, cron_create, cron_delete, cron_list, loop_create, reminder_create
)
from .core.checkpoints import (
    get_checkpoint_manager, get_deep_link_manager,
    checkpoint_create, checkpoint_list, checkpoint_restore, checkpoint_delete,
    deeplink_create, deeplink_resolve, deeplink_list
)
from .core.headless import run_headless_sync, HeadlessConfig
from .core.rag import index_directory, start_watcher, retrieve_context
from .core.cache import check_cache, save_to_cache

app = typer.Typer(help="MyCode: Open-Source Agentic CLI")
console = Console()

# Sub-apps for organized commands
hooks_app = typer.Typer(help="Hook system management")
scheduler_app = typer.Typer(help="Scheduler and automation")
checkpoint_app = typer.Typer(help="Checkpointing and rewind")
deeplink_app = typer.Typer(help="Deep links for session sharing")
headless_app = typer.Typer(help="Headless mode for CI/CD")

app.add_typer(hooks_app, name="hooks")
app.add_typer(scheduler_app, name="scheduler")
app.add_typer(checkpoint_app, name="checkpoint")
app.add_typer(deeplink_app, name="deeplink")
app.add_typer(headless_app, name="headless")


@app.command()
def main():
    """Start the MyCode interactive CLI session."""
    console.print(Panel.fit(
        "[bold green]MyCode v0.5.0 (Production)[/bold green]\n"
        "[dim]Open-Source Agentic CLI | Powered by NVIDIA Nemotron[/dim]",
        border_style="blue"
    ))

    api_key = ensure_config()
    client = NemotronClient(api_key)
    agent = Agent(client)

    # --- PHASE 4: RAG INITIALIZATION ---
    cwd = Path.cwd()
    index_directory(cwd)
    start_watcher(cwd)

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


# Hook commands
@hooks_app.command("list")
def hooks_list():
    """List all configured hooks."""
    registry = get_hook_registry()
    if not registry.hooks:
        console.print("[dim]No hooks configured[/dim]")
        return

    table = Table(title="Configured Hooks")
    table.add_column("#", style="cyan")
    table.add_column("Event", style="green")
    table.add_column("Matcher", style="yellow")
    table.add_column("Handler", style="magenta")
    table.add_column("Enabled", style="bold")

    for i, hook in enumerate(registry.hooks):
        table.add_row(
            str(i),
            hook.event.value,
            hook.matcher or "any",
            hook.handler.value,
            "✅" if hook.enabled else "❌"
        )

    console.print(table)


@hooks_app.command("add")
def hooks_add(
    event: str = typer.Argument(..., help="Hook event (e.g., PreToolUse)"),
    handler: str = typer.Argument(..., help="Handler type (command, http, mcp_tool, prompt_based, agent_based)"),
    matcher: str = typer.Option(None, "--matcher", "-m", help="Tool name to match"),
    command: str = typer.Option(None, "--command", "-c", help="Shell command for command handler"),
    url: str = typer.Option(None, "--url", "-u", help="Webhook URL for HTTP handler"),
    payload: str = typer.Option(None, "--payload", "-p", help="Payload template for HTTP handler"),
    timeout: int = typer.Option(30, "--timeout", "-t", help="Timeout in seconds"),
):
    """Add a new hook."""
    try:
        hook_event = HookEvent(event)
        hook_handler = HookHandlerType(handler)
    except ValueError:
        console.print("[red]Invalid event or handler type[/red]")
        return

    hook = HookConfig(
        event=HookEvent(event),
        handler=HookHandlerType(handler),
        matcher=matcher,
        command=command,
        url=url,
        payload=payload,
        timeout=timeout
    )

    registry = get_hook_registry()
    registry.add_hook(hook)
    console.print(f"[green]✓ Hook added: {event} → {handler}[/green]")


@hooks_app.command("remove")
def hooks_remove(index: int = typer.Argument(..., help="Hook index to remove")):
    """Remove a hook by index."""
    registry = get_hook_registry()
    if registry.remove_hook(index):
        console.print(f"[green]✓ Hook at index {index} removed[/green]")
    else:
        console.print("[red]Invalid index[/red]")


@hooks_app.command("test")
def hooks_test(
    event: str = typer.Argument(..., help="Event to test"),
    tool: str = typer.Option(None, "--tool", "-t", help="Tool name"),
    args: str = typer.Option("{}", "--args", "-a", help="Tool arguments as JSON"),
):
    """Test fire a hook event."""
    try:
        hook_event = HookEvent(event)
    except ValueError:
        console.print("[red]Invalid event[/red]")
        return

    import json
    tool_args = json.loads(args) if args else {}

    from mycode.core.hooks import HookContext
    context = HookContext(
        event=HookEvent(event),
        tool_name=tool,
        tool_args=tool_args
    )

    results = fire_hook_sync(HookEvent(event), context)

    console.print(f"[green]Fired {len(results)} hook(s)[/green]")
    for r in results:
        if r["success"]:
            console.print(f"  ✅ {r['hook'].event.value} → {r['result']}")
        else:
            console.print(f"  ❌ {r['hook'].event.value} → {r['error']}")


# Scheduler commands
@scheduler_app.command("cron")
def scheduler_cron(
    name: str = typer.Argument(..., help="Job name"),
    schedule: str = typer.Argument(..., help="Cron expression (e.g., '0 9 * * *')"),
    prompt: str = typer.Argument(..., help="Prompt to run"),
    max_runs: int = typer.Option(None, "--max-runs", "-m", help="Maximum runs"),
):
    """Create a cron job."""
    job_id = cron_create(name, schedule, prompt, max_runs)
    console.print(f"[green]✓ Cron job created: {job_id}[/green]")


@scheduler_app.command("cron-list")
def scheduler_cron_list():
    """List all cron jobs."""
    jobs = cron_list()
    if not jobs:
        console.print("[dim]No cron jobs[/dim]")
        return

    table = Table(title="Cron Jobs")
    table.add_column("ID", style="cyan")
    table.add_column("Name", style="green")
    table.add_column("Schedule", style="yellow")
    table.add_column("Prompt", style="magenta")
    table.add_column("Enabled", style="bold")
    table.add_column("Next Run", style="blue")
    table.add_column("Runs", style="cyan")

    for job in jobs:
        table.add_row(
            job["id"], job["name"], job["schedule"],
            job["prompt"], "✅" if job["enabled"] else "❌",
            job["next_run"], str(job["run_count"])
        )

    console.print(table)


@scheduler_app.command("cron-delete")
def scheduler_cron_delete(job_id: str = typer.Argument(..., help="Job ID to delete")):
    """Delete a cron job."""
    if cron_delete(job_id):
        console.print(f"[green]✓ Cron job {job_id} deleted[/green]")
    else:
        console.print("[red]Job not found[/red]")


@scheduler_app.command("loop")
def scheduler_loop(
    name: str = typer.Argument(..., help="Job name"),
    interval: int = typer.Argument(..., help="Interval in seconds"),
    prompt: str = typer.Argument(..., help="Prompt to run"),
    max_runs: int = typer.Option(None, "--max-runs", "-m", help="Maximum runs"),
):
    """Create a loop job (run every N seconds)."""
    job_id = loop_create(name, interval, prompt, max_runs)
    console.print(f"[green]✓ Loop job created: {job_id}[/green]")


@scheduler_app.command("reminder")
def scheduler_reminder(
    name: str = typer.Argument(..., help="Job name"),
    when: str = typer.Argument(..., help="ISO datetime (e.g., 2024-12-31T23:59:00)"),
    prompt: str = typer.Argument(..., help="Prompt to run"),
):
    """Create a one-time reminder."""
    job_id = reminder_create(name, when, prompt)
    console.print(f"[green]✓ Reminder created: {job_id}[/green]")


# Checkpoint commands
@checkpoint_app.command("list")
def checkpoint_list_cmd(session_id: str = typer.Option(None, "--session", "-s", help="Filter by session")):
    """List all checkpoints."""
    checkpoints = checkpoint_list(session_id)
    if not checkpoints:
        console.print("[dim]No checkpoints[/dim]")
        return

    table = Table(title="Checkpoints")
    table.add_column("ID", style="cyan")
    table.add_column("Name", style="green")
    table.add_column("Created", style="yellow")
    table.add_column("Messages", style="magenta")
    table.add_column("Tool Calls", style="cyan")
    table.add_column("Files", style="blue")

    for cp in checkpoints:
        table.add_row(
            cp["id"], cp["name"], cp["created_at"][:19],
            str(cp["message_count"]), str(cp["tool_calls_count"]), str(cp["files_modified"])
        )

    console.print(table)


@checkpoint_app.command("restore")
def checkpoint_restore_cmd(checkpoint_id: str = typer.Argument(..., help="Checkpoint ID to restore")):
    """Restore a checkpoint."""
    state = checkpoint_restore(checkpoint_id)
    if state:
        console.print(f"[green]✓ Checkpoint {checkpoint_id} restored[/green]")
        console.print(f"  Messages: {len(state.get('messages', []))}")
        console.print(f"  Tool calls: {len(state.get('tool_history', []))}")
        console.print(f"  Files: {len(state.get('file_hashes', {}))}")
    else:
        console.print("[red]Checkpoint not found[/red]")


@checkpoint_app.command("delete")
def checkpoint_delete_cmd(checkpoint_id: str = typer.Argument(..., help="Checkpoint ID to delete")):
    """Delete a checkpoint."""
    if checkpoint_delete(checkpoint_id):
        console.print(f"[green]✓ Checkpoint {checkpoint_id} deleted[/green]")
    else:
        console.print("[red]Checkpoint not found[/red]")


# Deep link commands
@deeplink_app.command("create")
def deeplink_create_cmd(
    session_id: str = typer.Argument(..., help="Session ID"),
    cwd: str = typer.Argument(..., help="Working directory"),
    name: str = typer.Option("", "--name", "-n", help="Link name"),
):
    """Create a deep link for a session."""
    link = deeplink_create(session_id, cwd, name)
    console.print(f"[green]✓ Deep link created: {link}[/green]")


@deeplink_app.command("resolve")
def deeplink_resolve_cmd(link_id: str = typer.Argument(..., help="Link ID to resolve")):
    """Resolve a deep link."""
    data = deeplink_resolve(link_id)
    if data:
        console.print(f"Session: {data['session_id']}")
        console.print(f"CWD: {data['cwd']}")
        console.print(f"Name: {data['name']}")
        console.print(f"Created: {data['created_at']}")
    else:
        console.print("[red]Link not found[/red]")


@deeplink_app.command("list")
def deeplink_list_cmd():
    """List all deep links."""
    links = deeplink_list()
    if not links:
        console.print("[dim]No deep links[/dim]")
        return

    table = Table(title="Deep Links")
    table.add_column("ID", style="cyan")
    table.add_column("Session", style="green")
    table.add_column("CWD", style="yellow")
    table.add_column("Name", style="magenta")
    table.add_column("Created", style="blue")

    for link in links:
        table.add_row(
            link["id"], link["session_id"][:8], link["cwd"],
            link["name"], link["created_at"][:19]
        )

    console.print(table)


# Headless commands
@headless_app.command("run")
def headless_run(
    prompt: str = typer.Argument(..., help="Prompt to run"),
    json_output: bool = typer.Option(True, "--json/--no-json", help="JSON output"),
    stream: bool = typer.Option(False, "--stream", help="Stream output"),
    output: str = typer.Option(None, "--output", "-o", help="Output file"),
):
    """Run a prompt in headless mode."""
    config = HeadlessConfig(
        json_output=json_output,
        stream_output=stream,
        output_file=output
    )

    results = run_headless_sync([prompt], config)
    if results:
        r = results[0]
        if json_output:
            import json
            console.print(json.dumps({
                "success": r.success,
                "response": r.response,
                "reasoning": r.reasoning,
                "tool_calls": r.tool_calls,
                "iterations": r.iterations,
                "duration": r.duration,
                "error": r.error
            }, indent=2))
        else:
            console.print(f"Success: {r.success}")
            console.print(f"Response: {r.response}")
            if r.reasoning:
                console.print(f"Reasoning: {r.reasoning}")
            if r.tool_calls:
                console.print(f"Tools: {len(r.tool_calls)}")
            if r.error:
                console.print(f"Error: {r.error}")


@headless_app.command("batch")
def headless_batch(
    prompts_file: str = typer.Argument(..., help="File with prompts (one per line)"),
    output: str = typer.Option(None, "--output", "-o", help="Output file"),
):
    """Run multiple prompts from a file."""
    with open(prompts_file, 'r') as f:
        prompts = [line.strip() for line in f if line.strip()]

    if not prompts:
        console.print("[red]No prompts in file[/red]")
        return

    config = HeadlessConfig(output_file=output)
    results = run_headless_sync(prompts, HeadlessConfig(output_file=output))

    console.print(f"[green]Processed {len(results)} prompts[/green]")


if __name__ == "__main__":
    app()
