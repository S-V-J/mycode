import typer
from pathlib import Path
from typing import List
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
from .core.mcp import (
    get_mcp_client, mcp_add, mcp_remove, mcp_list, mcp_connect, mcp_disconnect,
    mcp_tools, mcp_resources, mcp_prompts
)
from .core.plugins import (
    PluginManager, PluginManifest, PluginType, get_plugin_manager
)
from .core.skills import (
    SkillRegistry, SkillExecutor, SkillManifest, SkillArgumentType, get_skill_registry, get_skill_executor
)
from .core.artifacts import (
    ArtifactManager, ArtifactType, get_artifact_manager
)
from .core.channels import (
    ChannelServer, PermissionRelay, PermissionType, get_channel_server, get_permission_relay
)

app = typer.Typer(help="MyCode: Open-Source Agentic CLI")
console = Console()

# Sub-apps for organized commands
hooks_app = typer.Typer(help="Hook system management")
scheduler_app = typer.Typer(help="Scheduler and automation")
checkpoint_app = typer.Typer(help="Checkpointing and rewind")
deeplink_app = typer.Typer(help="Deep links for session sharing")
headless_app = typer.Typer(help="Headless mode for CI/CD")
mcp_app = typer.Typer(help="MCP (Model Context Protocol) management")
plugin_app = typer.Typer(help="Plugin management")
skill_app = typer.Typer(help="Skill management")
artifact_app = typer.Typer(help="Artifact management")
channel_app = typer.Typer(help="Channel/webhook management")

app.add_typer(hooks_app, name="hooks")
app.add_typer(scheduler_app, name="scheduler")
app.add_typer(checkpoint_app, name="checkpoint")
app.add_typer(deeplink_app, name="deeplink")
app.add_typer(headless_app, name="headless")
app.add_typer(mcp_app, name="mcp")
app.add_typer(plugin_app, name="plugin")
app.add_typer(skill_app, name="skill")
app.add_typer(artifact_app, name="artifact")
app.add_typer(channel_app, name="channel")


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


# MCP commands
@mcp_app.command("add")
def mcp_add_cmd(
    name: str = typer.Argument(..., help="Server name"),
    transport: str = typer.Argument(..., help="Transport type (http, sse, stdio, websocket)"),
    url: str = typer.Option(None, "--url", "-u", help="URL for HTTP/SSE/WebSocket"),
    command: str = typer.Option(None, "--command", "-c", help="Command for stdio transport"),
    args: str = typer.Option("", "--args", "-a", help="Arguments for stdio (space-separated)"),
):
    """Add an MCP server."""
    from .core.mcp import mcp_add
    args_list = args.split() if args else []
    if mcp_add(name, transport, url=url, command=command, args=args.split() if args else []):
        console.print(f"[green]✓ MCP server '{name}' added[/green]")
    else:
        console.print("[red]Failed to add server (name may already exist)[/red]")


@mcp_app.command("remove")
def mcp_remove_cmd(name: str = typer.Argument(..., help="Server name to remove")):
    """Remove an MCP server."""
    from .core.mcp import mcp_remove
    if mcp_remove(name):
        console.print(f"[green]✓ MCP server '{name}' removed[/green]")
    else:
        console.print("[red]Server not found[/red]")


@mcp_app.command("list")
def mcp_list_cmd():
    """List all MCP servers."""
    from .core.mcp import mcp_list
    servers = mcp_list()
    if not servers:
        console.print("[dim]No MCP servers configured[/dim]")
        return

    table = Table(title="MCP Servers")
    table.add_column("Name", style="cyan")
    table.add_column("Transport", style="green")
    table.add_column("URL/Command", style="yellow")
    table.add_column("Enabled", style="bold")

    for s in servers:
        url_cmd = s.get("url") or s.get("command") or ""
        table.add_row(s["name"], s["transport"], url_cmd[:50], "✅" if s["enabled"] else "❌")

    console.print(table)


@mcp_app.command("connect")
def mcp_connect_cmd(name: str = typer.Argument(..., help="Server name to connect")):
    """Connect to an MCP server."""
    import asyncio
    from .core.mcp import mcp_connect
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(asyncio.run, mcp_connect(name))
                result = future.result()
        else:
            result = loop.run_until_complete(mcp_connect(name))
    except RuntimeError:
        result = asyncio.run(mcp_connect(name))

    if result:
        console.print(f"[green]✓ Connected to '{name}'[/green]")
    else:
        console.print("[red]Failed to connect[/red]")


@mcp_app.command("disconnect")
def mcp_disconnect_cmd(name: str = typer.Argument(..., help="Server name to disconnect")):
    """Disconnect from an MCP server."""
    import asyncio
    from .core.mcp import mcp_disconnect
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(asyncio.run, mcp_disconnect(name))
                result = future.result()
        else:
            result = loop.run_until_complete(mcp_disconnect(name))
    except RuntimeError:
        result = asyncio.run(mcp_disconnect(name))

    if result:
        console.print(f"[green]✓ Disconnected from '{name}'[/green]")
    else:
        console.print("[red]Server not connected or not found[/red]")


@mcp_app.command("tools")
def mcp_tools_cmd():
    """List all available MCP tools."""
    from .core.mcp import mcp_tools
    tools = mcp_tools()
    if not tools:
        console.print("[dim]No MCP tools available[/dim]")
        return

    table = Table(title="MCP Tools")
    table.add_column("Name", style="cyan")
    table.add_column("Description", style="green")
    table.add_column("Server", style="yellow")

    for t in tools:
        table.add_row(t["name"], t["description"][:50], t["server"])

    console.print(table)


@mcp_app.command("resources")
def mcp_resources_cmd():
    """List all available MCP resources."""
    from .core.mcp import mcp_resources
    resources = mcp_resources()
    if not resources:
        console.print("[dim]No MCP resources available[/dim]")
        return

    table = Table(title="MCP Resources")
    table.add_column("URI", style="cyan")
    table.add_column("Name", style="green")
    table.add_column("Description", style="yellow")
    table.add_column("Server", style="blue")

    for r in resources:
        table.add_row(r["uri"], r["name"], r["description"] or "", r["server"])

    console.print(table)


@mcp_app.command("prompts")
def mcp_prompts_cmd():
    """List all available MCP prompts."""
    from .core.mcp import mcp_prompts
    prompts = mcp_prompts()
    if not prompts:
        console.print("[dim]No MCP prompts available[/dim]")
        return

    table = Table(title="MCP Prompts")
    table.add_column("Name", style="cyan")
    table.add_column("Description", style="green")
    table.add_column("Server", style="yellow")

    for p in prompts:
        table.add_row(p["name"], p["description"][:50], p["server"])

    console.print(table)


# Plugin commands
@plugin_app.command("list")
def plugin_list(scope: str = typer.Option("all", "--scope", "-s", help="Scope: user, project, all")):
    """List installed plugins."""
    from .core.plugins import get_plugin_manager
    from pathlib import Path
    manager = get_plugin_manager(Path.home() / ".mycode", Path.cwd())
    plugins = manager.list_plugins(scope if scope != "all" else None)
    if not plugins:
        console.print("[dim]No plugins installed[/dim]")
        return

    table = Table(title="Installed Plugins")
    table.add_column("Name", style="cyan")
    table.add_column("Version", style="green")
    table.add_column("Type", style="yellow")
    table.add_column("Status", style="bold")
    table.add_column("Scope", style="blue")
    table.add_column("Description", style="white")

    for p in plugins:
        status = "✅" if p.status.value == "enabled" else "❌" if p.status.value == "disabled" else "📦"
        table.add_row(p.manifest.name, p.manifest.version, p.manifest.plugin_type.value, status, p.config.get("scope", "user"), p.manifest.description[:50])

    console.print(table)


@plugin_app.command("install")
def plugin_install(
    name: str = typer.Argument(..., help="Plugin name"),
    version: str = typer.Option("latest", "--version", "-v", help="Version to install"),
    marketplace: str = typer.Option(None, "--marketplace", "-m", help="Marketplace name"),
    scope: str = typer.Option("user", "--scope", "-s", help="Install scope: user or project"),
    force: bool = typer.Option(False, "--force", "-f", help="Force reinstall"),
):
    """Install a plugin."""
    import asyncio
    from .core.plugins import get_plugin_manager
    from pathlib import Path
    manager = get_plugin_manager(Path.home() / ".mycode", Path.cwd())
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(asyncio.run, manager.install(name, version, marketplace, scope, force))
                result = future.result()
        else:
            result = loop.run_until_complete(manager.install(name, version, marketplace, scope, force))
    except RuntimeError:
        result = asyncio.run(manager.install(name, version, marketplace, scope, force))

    if not result:
        console.print("[red]Installation failed[/red]")


@plugin_app.command("uninstall")
def plugin_uninstall(name: str = typer.Argument(..., help="Plugin name"), scope: str = typer.Option("user", "--scope", "-s", help="Scope")):
    """Uninstall a plugin."""
    from .core.plugins import get_plugin_manager
    from pathlib import Path
    manager = get_plugin_manager(Path.home() / ".mycode", Path.cwd())
    if manager.uninstall(name, scope):
        console.print(f"[green]✓ Uninstalled {name}[/green]")
    else:
        console.print("[red]Failed to uninstall[/red]")


@plugin_app.command("enable")
def plugin_enable(name: str = typer.Argument(..., help="Plugin name")):
    """Enable a plugin."""
    from .core.plugins import get_plugin_manager
    from pathlib import Path
    manager = get_plugin_manager(Path.home() / ".mycode", Path.cwd())
    if manager.enable(name):
        console.print(f"[green]✓ Enabled {name}[/green]")
    else:
        console.print("[red]Failed to enable[/red]")


@plugin_app.command("disable")
def plugin_disable(name: str = typer.Argument(..., help="Plugin name")):
    """Disable a plugin."""
    from .core.plugins import get_plugin_manager
    from pathlib import Path
    manager = get_plugin_manager(Path.home() / ".mycode", Path.cwd())
    if manager.disable(name):
        console.print(f"[green]✓ Disabled {name}[/green]")
    else:
        console.print("[red]Failed to disable[/red]")


@plugin_app.command("update")
def plugin_update(name: str = typer.Argument(..., help="Plugin name")):
    """Update a plugin to latest version."""
    import asyncio
    from .core.plugins import get_plugin_manager
    from pathlib import Path
    manager = get_plugin_manager(Path.home() / ".mycode", Path.cwd())
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(asyncio.run, manager.update(name))
                result = future.result()
        else:
            result = loop.run_until_complete(manager.update(name))
    except RuntimeError:
        result = asyncio.run(manager.update(name))

    if not result:
        console.print("[red]Update failed[/red]")


@plugin_app.command("search")
def plugin_search(query: str = typer.Argument("", help="Search query"), marketplace: str = typer.Option(None, "--marketplace", "-m", help="Marketplace name")):
    """Search for plugins in marketplaces."""
    import asyncio
    from .core.plugins import get_plugin_manager
    from pathlib import Path
    manager = get_plugin_manager(Path.home() / ".mycode", Path.cwd())
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(asyncio.run, manager.marketplace_manager.search_plugins(query, marketplace))
                results = future.result()
        else:
            results = loop.run_until_complete(manager.marketplace_manager.search_plugins(query, marketplace))
    except RuntimeError:
        results = asyncio.run(manager.marketplace_manager.search_plugins(query, marketplace))

    if not results:
        console.print("[dim]No plugins found[/dim]")
        return

    table = Table(title="Plugin Search Results")
    table.add_column("Name", style="cyan")
    table.add_column("Version", style="green")
    table.add_column("Marketplace", style="yellow")
    table.add_column("Description", style="white")

    for p in results[:20]:
        table.add_row(p.name, p.version, p.marketplace, p.description[:60])

    console.print(table)


@plugin_app.command("marketplace-add")
def plugin_marketplace_add(
    name: str = typer.Argument(..., help="Marketplace name"),
    type: str = typer.Argument(..., help="Type: github, local, npm"),
    url: str = typer.Argument(..., help="URL or path"),
    auth_token: str = typer.Option(None, "--token", "-t", help="Auth token"),
):
    """Add a plugin marketplace."""
    from .core.plugins import get_plugin_manager, MarketplaceConfig, MarketplaceType
    from pathlib import Path
    manager = get_plugin_manager(Path.home() / ".mycode", Path.cwd())
    config = MarketplaceConfig(name=name, type=MarketplaceType(type), url=url, auth_token=auth_token)
    if manager.marketplace_manager.add_marketplace(config):
        console.print(f"[green]✓ Marketplace '{name}' added[/green]")
    else:
        console.print("[red]Failed to add marketplace[/red]")


@plugin_app.command("marketplace-list")
def plugin_marketplace_list():
    """List configured marketplaces."""
    from .core.plugins import get_plugin_manager
    from pathlib import Path
    manager = get_plugin_manager(Path.home() / ".mycode", Path.cwd())
    marketplaces = manager.marketplace_manager.list_marketplaces()
    if not marketplaces:
        console.print("[dim]No marketplaces configured[/dim]")
        return

    table = Table(title="Plugin Marketplaces")
    table.add_column("Name", style="cyan")
    table.add_column("Type", style="green")
    table.add_column("URL", style="yellow")
    table.add_column("Priority", style="blue")
    table.add_column("Enabled", style="bold")

    for mp in marketplaces:
        table.add_row(mp.name, mp.type.value, mp.url, str(mp.priority), "✅" if mp.enabled else "❌")

    console.print(table)


@plugin_app.command("marketplace-remove")
def plugin_marketplace_remove(name: str = typer.Argument(..., help="Marketplace name")):
    """Remove a marketplace."""
    from .core.plugins import get_plugin_manager
    from pathlib import Path
    manager = get_plugin_manager(Path.home() / ".mycode", Path.cwd())
    if manager.marketplace_manager.remove_marketplace(name):
        console.print(f"[green]✓ Marketplace '{name}' removed[/green]")
    else:
        console.print("[red]Marketplace not found[/red]")


# Skill commands
@skill_app.command("list")
def skill_list(scope: str = typer.Option("all", "--scope", "-s", help="Scope: user, project, builtin, all")):
    """List available skills."""
    from .core.skills import get_skill_registry
    from pathlib import Path
    registry = get_skill_registry(Path.home() / ".mycode", Path.cwd())
    skills = registry.list_skills()
    if scope != "all":
        skills = [s for s in skills if s.scope.value == scope]

    if not skills:
        console.print("[dim]No skills found[/dim]")
        return

    table = Table(title="Available Skills")
    table.add_column("Name", style="cyan")
    table.add_column("Command", style="green")
    table.add_column("Version", style="yellow")
    table.add_column("Scope", style="blue")
    table.add_column("Status", style="bold")
    table.add_column("Description", style="white")

    for s in skills:
        status = "✅" if s.enabled else "❌"
        table.add_row(s.manifest.name, s.manifest.command, s.manifest.version, s.scope.value, status, s.manifest.description[:50])

    console.print(table)


@skill_app.command("enable")
def skill_enable(name: str = typer.Argument(..., help="Skill name")):
    """Enable a skill."""
    from .core.skills import get_skill_registry
    from pathlib import Path
    registry = get_skill_registry(Path.home() / ".mycode", Path.cwd())
    if registry.enable_skill(name):
        console.print(f"[green]✓ Enabled {name}[/green]")
    else:
        console.print("[red]Failed to enable[/red]")


@skill_app.command("disable")
def skill_disable(name: str = typer.Argument(..., help="Skill name")):
    """Disable a skill."""
    from .core.skills import get_skill_registry
    from pathlib import Path
    registry = get_skill_registry(Path.home() / ".mycode", Path.cwd())
    if registry.disable_skill(name):
        console.print(f"[green]✓ Disabled {name}[/green]")
    else:
        console.print("[red]Failed to disable[/red]")


@skill_app.command("run")
def skill_run(
    name: str = typer.Argument(..., help="Skill name or command"),
    args: str = typer.Option("", "--args", "-a", help="Arguments as JSON"),
    raw_args: List[str] = typer.Argument(None, help="Raw arguments"),
):
    """Run a skill."""
    import asyncio
    import json
    from .core.skills import get_skill_registry, get_skill_executor
    from pathlib import Path
    registry = get_skill_registry(Path.home() / ".mycode", Path.cwd())
    executor = get_skill_executor(registry, Path.home() / ".mycode", Path.cwd())

    # Resolve skill name (could be command)
    skill = registry.get_skill(name)
    if not skill:
        # Try by command
        commands = registry.get_skill_commands()
        if name in commands:
            skill = commands[name]
        else:
            console.print(f"[red]Skill '{name}' not found[/red]")
            return

    if not skill.enabled:
        console.print(f"[red]Skill '{name}' is disabled[/red]")
        return

    # Parse arguments
    parsed_args = {}
    if args:
        try:
            parsed_args = json.loads(args)
        except json.JSONDecodeError:
            console.print("[red]Invalid JSON arguments[/red]")
            return

    # Also parse raw args
    if raw_args:
        parsed_args.update(executor.parse_arguments(skill.manifest.name, raw_args))

    # Execute
    result = executor.execute(skill.manifest.name, parsed_args)

    if result.success:
        console.print(f"[green]✓ Skill executed successfully[/green]")
        if result.output is not None:
            console.print(json.dumps(result.output, indent=2, default=str))
    else:
        console.print(f"[red]Skill failed: {result.error}[/red]")


@skill_app.command("create")
def skill_create(
    name: str = typer.Argument(..., help="Skill name"),
    template: str = typer.Option("basic", "--template", "-t", help="Template: basic, file_processor, api_client, subagent"),
    output: str = typer.Option(None, "--output", "-o", help="Output directory"),
    description: str = typer.Option("", "--description", "-d", help="Skill description"),
):
    """Create a new skill from template."""
    from .core.skills import get_skill_registry, SkillCreator
    from pathlib import Path
    registry = get_skill_registry(Path.home() / ".mycode", Path.cwd())
    creator = SkillCreator(registry)

    output_dir = Path(output) if output else Path.cwd() / ".mycode" / "skills" / name
    if creator.create_from_template(template, name, output_dir, description=description):
        console.print(f"[green]✓ Skill '{name}' created at {output_dir}[/green]")
    else:
        console.print("[red]Failed to create skill[/red]")


@skill_app.command("test")
def skill_test(name: str = typer.Argument(..., help="Skill name")):
    """Run tests for a skill."""
    import asyncio
    from .core.skills import get_skill_registry, get_skill_executor, SkillEvaluator
    from pathlib import Path
    registry = get_skill_registry(Path.home() / ".mycode", Path.cwd())
    executor = get_skill_executor(registry, Path.home() / ".mycode", Path.cwd())
    evaluator = SkillEvaluator(executor)

    skill = registry.get_skill(name)
    if not skill:
        console.print(f"[red]Skill '{name}' not found[/red]")
        return

    # Create a basic test suite
    suite = evaluator.create_suite(name)
    suite.add_test_simple("basic_execution", {}, expected_output={"success": True})

    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor_pool:
                future = executor_pool.submit(asyncio.run, evaluator.run_suite(name))
                results = future.result()
        else:
            results = loop.run_until_complete(evaluator.run_suite(name))
    except RuntimeError:
        results = asyncio.run(evaluator.run_suite(name))

    console.print(evaluator.generate_report({name: results}))


# Artifact commands
@artifact_app.command("list")
def artifact_list():
    """List saved artifacts."""
    from .core.artifacts import get_artifact_manager
    from pathlib import Path
    manager = get_artifact_manager(Path.home() / ".mycode")
    artifacts = manager.list_artifacts()
    if not artifacts:
        console.print("[dim]No artifacts saved[/dim]")
        return

    table = Table(title="Saved Artifacts")
    table.add_column("ID", style="cyan")
    table.add_column("Type", style="green")
    table.add_column("Title", style="yellow")

    for a in artifacts:
        table.add_row(a.id, a.type.value, a.title)

    console.print(table)


@artifact_app.command("render")
def artifact_render(artifact_id: str = typer.Argument(..., help="Artifact ID")):
    """Render an artifact."""
    from .core.artifacts import get_artifact_manager
    from pathlib import Path
    manager = get_artifact_manager(Path.home() / ".mycode")
    manager.render_artifact_by_id(artifact_id)


@artifact_app.command("delete")
def artifact_delete(artifact_id: str = typer.Argument(..., help="Artifact ID")):
    """Delete an artifact."""
    from .core.artifacts import get_artifact_manager
    from pathlib import Path
    manager = get_artifact_manager(Path.home() / ".mycode")
    if manager.delete_artifact(artifact_id):
        console.print(f"[green]✓ Artifact '{artifact_id}' deleted[/green]")
    else:
        console.print("[red]Artifact not found[/red]")


# Channel commands
@channel_app.command("server-start")
def channel_server_start(
    host: str = typer.Option("localhost", "--host", help="Host to bind"),
    port: int = typer.Option(8765, "--port", "-p", help="Port to bind"),
):
    """Start the channel server."""
    import asyncio
    from .core.channels import ChannelServer, get_channel_server
    server = get_channel_server(host, port)

    console.print(f"[green]Starting channel server on {host}:{port}...[/green]")
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            loop.create_task(server.start())
        else:
            loop.run_until_complete(server.start())
        console.print("[green]Server started. Press Ctrl+C to stop.[/green]")
        loop.run_forever()
    except KeyboardInterrupt:
        console.print("\n[yellow]Stopping server...[/yellow]")
        loop.run_until_complete(server.stop())


@channel_app.command("webhook-add")
def channel_webhook_add(
    webhook_id: str = typer.Argument(..., help="Webhook ID"),
    path: str = typer.Argument(..., help="URL path"),
    secret: str = typer.Option(None, "--secret", "-s", help="HMAC secret"),
):
    """Add a webhook endpoint."""
    from .core.channels import get_channel_server, WebhookConfig
    server = get_channel_server()
    config = WebhookConfig(path=path, secret=secret)
    server.register_webhook(webhook_id, config)
    console.print(f"[green]✓ Webhook '{webhook_id}' added at {path}[/green]")


@channel_app.command("webhook-list")
def channel_webhook_list():
    """List webhook endpoints."""
    from .core.channels import get_channel_server
    server = get_channel_server()
    if not server.webhooks:
        console.print("[dim]No webhooks configured[/dim]")
        return

    table = Table(title="Webhooks")
    table.add_column("ID", style="cyan")
    table.add_column("Path", style="green")
    table.add_column("Secret", style="yellow")

    for wid, config in server.webhooks.items():
        table.add_row(wid, config.path, "***" if config.secret else "none")

    console.print(table)


@channel_app.command("emit")
def channel_emit(
    event_type: str = typer.Argument(..., help="Event type"),
    source: str = typer.Argument(..., help="Event source"),
    payload: str = typer.Argument("{}", help="Payload as JSON"),
):
    """Emit an event to channel."""
    import asyncio
    import json
    from .core.channels import get_channel_server, ChannelEvent, EventType
    server = get_channel_server()

    try:
        event_type_enum = EventType(event_type)
    except ValueError:
        console.print(f"[red]Invalid event type. Valid: {[e.value for e in EventType]}[/red]")
        return

    try:
        payload_dict = json.loads(payload)
    except json.JSONDecodeError:
        console.print("[red]Invalid JSON payload[/red]")
        return

    event = ChannelEvent.create(event_type_enum, source, payload_dict)

    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            loop.create_task(server.emit(event))
        else:
            loop.run_until_complete(server.emit(event))
        console.print("[green]✓ Event emitted[/green]")
    except RuntimeError:
        asyncio.run(server.emit(event))
        console.print("[green]✓ Event emitted[/green]")


if __name__ == "__main__":
    app()
