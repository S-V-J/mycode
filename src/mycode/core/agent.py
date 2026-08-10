import json
import time
from pathlib import Path
from typing import Optional, Callable, Awaitable
from rich.console import Console
from rich.markdown import Markdown
from rich.prompt import Confirm
from .llm_client import NemotronClient
from mycode.tools.schemas import TOOLS
from mycode.tools.bash import execute_bash
from mycode.tools.file_ops import read_file, write_file, edit_file
from mycode.tools.web import web_search, fetch_url
from .cache import check_cache, save_to_cache
from .rag import retrieve_context
from .config import find_mycode_md
from .modes import (
    AgentMode,
    ToolCallPlan,
    ExecutionPlan,
    is_destructive_tool,
    is_destructive_bash
)

console = Console()

BASE_SYSTEM_PROMPT = """You are MyCode, an elite autonomous coding assistant. You have access to tools to interact with the local WSL system and the web. Think step-by-step, use tools to gather information or make changes, and provide a final markdown response when done.

When generating tool calls, provide clear descriptions of what each tool will do."""

PLAN_MODE_PROMPT = """You are in PLAN MODE. Generate a detailed execution plan with tool calls, but DO NOT execute them.
Instead, output your plan as a structured response that will be presented to the user for approval.

Format your response as:
## Plan Summary
[Brief summary of what you'll do]

## Steps
1. **Tool**: [tool_name] - [description of what this step does]
   Args: [JSON args]
   Destructive: [true/false]

2. **Tool**: [tool_name] - [description]
   Args: [JSON args]
   Destructive: [true/false]

...

The user will review and approve/reject this plan."""

MANUAL_MODE_PROMPT = """You are in MANUAL MODE. Act as a pair-programmer. Suggest code, commands, and explanations in the chat.
DO NOT use any tools - they are disabled. Provide clear, actionable guidance that the user can execute themselves."""

AEROPLANE_MODE_PROMPT = """You are in AEROPLANE MODE (Offline). You have NO access to external APIs.
Rely ONLY on:
1. Local Semantic Cache (previous solutions)
2. Local RAG (codebase context)
3. Your internal knowledge

Do not attempt to call any external tools or APIs."""


def get_dynamic_params(user_input: str, iteration: int) -> dict:
    """
    Context-Aware Dynamic Routing: Scales parameters based on prompt complexity and ReAct depth.
    """
    # Base parameters (Fast, deterministic, avoids rate limits)
    params = {
        "temperature": 0.2,
        "max_tokens": 4096,
        "reasoning_budget": 2048
    }

    # Complexity triggers
    complex_keywords = [
        "refactor", "architecture", "debug", "traceback", "complex",
        "entire", "all files", "multi-file", "optimize", "security",
        "vulnerability", "design", "plan", "why", "how does", "analyze"
    ]

    is_complex = (
        len(user_input) > 150 or
        any(kw in user_input.lower() for kw in complex_keywords) or
        iteration >= 2  # Deep in the ReAct loop means it's struggling or doing multi-step work
    )

    if is_complex:
        # UNLOCK RAW POWER (Maximum capabilities)
        params["temperature"] = 1.0
        params["max_tokens"] = 16384
        params["reasoning_budget"] = 16384

    return params


class Agent:
    def __init__(
        self,
        client: NemotronClient,
        mode: AgentMode = AgentMode.AUTO,
        accept_edits: bool = True,
        approval_callback: Optional[Callable[[ExecutionPlan], Awaitable[bool]]] = None,
        diff_approval_callback: Optional[Callable[[str, str, str], Awaitable[bool]]] = None
    ):
        self.client = client
        self.mode = mode
        self.accept_edits = accept_edits
        self.approval_callback = approval_callback
        self.diff_approval_callback = diff_approval_callback

        # --- PHASE 5: PROJECT MEMORY INJECTION ---
        project_rules = find_mycode_md(Path.cwd())

        self.base_prompt = BASE_SYSTEM_PROMPT
        if project_rules:
            self.base_prompt += f"\n\nPROJECT RULES & CONTEXT (from MYCODE.md):\n{project_rules}"

        # Add mode-specific instructions
        if self.mode == AgentMode.PLAN:
            self.base_prompt += f"\n\n{PLAN_MODE_PROMPT}"
        elif self.mode == AgentMode.MANUAL:
            self.base_prompt += f"\n\n{MANUAL_MODE_PROMPT}"
        elif self.mode == AgentMode.AEROPLANE:
            self.base_prompt += f"\n\n{AEROPLANE_MODE_PROMPT}"

        self.messages = [
            {"role": "system", "content": self.base_prompt}
        ]

    def set_mode(self, mode: AgentMode):
        """Change the agent's operational mode."""
        self.mode = mode
        # Rebuild system prompt with new mode
        self.base_prompt = BASE_SYSTEM_PROMPT
        project_rules = find_mycode_md(Path.cwd())
        if project_rules:
            self.base_prompt += f"\n\nPROJECT RULES & CONTEXT (from MYCODE.md):\n{project_rules}"

        if self.mode == AgentMode.PLAN:
            self.base_prompt += f"\n\n{PLAN_MODE_PROMPT}"
        elif self.mode == AgentMode.MANUAL:
            self.base_prompt += f"\n\n{MANUAL_MODE_PROMPT}"
        elif self.mode == AgentMode.AEROPLANE:
            self.base_prompt += f"\n\n{AEROPLANE_MODE_PROMPT}"

        self.messages[0]["content"] = self.base_prompt

    def set_accept_edits(self, accept: bool):
        """Toggle accept edits mode."""
        self.accept_edits = accept

    def _get_available_tools(self) -> list:
        """Get tools available for current mode."""
        if self.mode == AgentMode.MANUAL:
            return []  # No tools in manual mode
        if self.mode == AgentMode.AEROPLANE:
            # In aeroplane mode, only allow local tools (no web)
            return [t for t in TOOLS if t["function"]["name"] not in ("web_search", "fetch_url")]
        return TOOLS

    def _should_check_permissions(self) -> bool:
        """Check if we should prompt for permission before executing tools."""
        return self.mode.requires_permission_check

    def _should_check_safety(self) -> bool:
        """Check if we should run safety checks on commands."""
        return self.mode.requires_safety_check

    def _build_execution_plan(self, tool_calls: list) -> ExecutionPlan:
        """Build an execution plan from tool calls for Plan Mode approval."""
        steps = []
        for tc in tool_calls:
            name = tc["function"]["name"]
            try:
                args = json.loads(tc["function"]["arguments"])
            except json.JSONDecodeError:
                args = {}

            is_destructive = is_destructive_tool(name, args)

            # Generate description based on tool
            descriptions = {
                "bash": f"Execute command: {args.get('command', '')[:100]}",
                "read_file": f"Read file: {args.get('path', '')}",
                "write_file": f"Write file: {args.get('path', '')}",
                "edit_file": f"Edit file: {args.get('path', '')}",
                "web_search": f"Search web for: {args.get('query', '')}",
                "fetch_url": f"Fetch URL: {args.get('url', '')}",
            }
            description = descriptions.get(name, f"Execute {name}")

            steps.append(ToolCallPlan(
                name=name,
                args=args,
                description=description,
                is_destructive=is_destructive
            ))

        # Generate summary
        tool_names = [s.name for s in steps]
        summary = f"Execute {len(steps)} tool call(s): {', '.join(tool_names)}"

        return ExecutionPlan(steps=steps, summary=summary)

    async def _request_plan_approval(self, plan: ExecutionPlan) -> bool:
        """Request user approval for the execution plan."""
        if self.approval_callback:
            return await self.approval_callback(plan)
        return False

    async def _request_diff_approval(self, path: str, old_content: str, new_content: str) -> bool:
        """Request user approval for a file diff."""
        if self.diff_approval_callback:
            return await self.diff_approval_callback(path, old_content, new_content)
        return False

    def _execute_tool(self, name: str, args: dict) -> str:
        """Execute a single tool and return observation."""
        if name == "bash":
            return execute_bash(args.get("command", ""))
        elif name == "read_file":
            return read_file(args.get("path", ""))
        elif name == "write_file":
            return write_file(args.get("path", ""), args.get("content", ""))
        elif name == "edit_file":
            return edit_file(args.get("path", ""), args.get("old_str", ""), args.get("new_str", ""))
        elif name == "web_search":
            return web_search(args.get("query", ""), args.get("max_results", 5))
        elif name == "fetch_url":
            return fetch_url(args.get("url", ""))
        else:
            return f"Error: Unknown tool {name}"

    def run(self, user_input: str):
        # --- PHASE 3: SEMANTIC CACHE INTERCEPTOR ---
        cached_result = check_cache(user_input)
        if cached_result:
            console.print(Markdown(cached_result["response"]))
            return

        # --- PHASE 4: AUTO-CONTEXT RAG INJECTION ---
        rag_context = retrieve_context(user_input)
        if rag_context:
            self.messages[0]["content"] = self.base_prompt + "\n\n" + rag_context
        else:
            self.messages[0]["content"] = self.base_prompt

        # --- STANDARD REACT LOOP (Cache Miss) ---
        self.messages.append({"role": "user", "content": user_input})
        final_response = ""
        executed_tools = []

        # Max 10 iterations to allow for deep, complex agentic workflows
        for i in range(10):
            # --- SMART SYSTEM: DYNAMIC PARAMETER ROUTING ---
            params = get_dynamic_params(user_input, i)
            console.print(f"[dim]⚙️ Smart Routing: temp={params['temperature']}, max_tokens={params['max_tokens']}, reasoning_budget={params['reasoning_budget']}[/dim]")

            available_tools = self._get_available_tools()
            content, tool_calls = self.client.stream_chat(self.messages, tools=available_tools, params=params)

            if tool_calls:
                self.messages.append({
                    "role": "assistant",
                    "content": content or None,
                    "tool_calls": [
                        {
                            "id": tc["id"],
                            "type": "function",
                            "function": {
                                "name": tc["function"]["name"],
                                "arguments": tc["function"]["arguments"]
                            }
                        } for tc in tool_calls
                    ]
                })

                # In PLAN MODE: Build plan and request approval
                if self.mode == AgentMode.PLAN:
                    plan = self._build_execution_plan(tool_calls)
                    console.print(f"\n[bold yellow]📋 Plan Mode: Generated execution plan with {len(plan.steps)} step(s)[/bold yellow]")
                    console.print(f"[dim]{plan.summary}[/dim]")

                    # Request approval (synchronous for now, will be async via callback)
                    approved = False
                    if self.approval_callback:
                        import asyncio
                        try:
                            loop = asyncio.get_event_loop()
                            if loop.is_running():
                                # Can't run async in sync context, store for later
                                console.print("[yellow]Plan approval requested - waiting for user...[/yellow]")
                                # For now, auto-approve in CLI mode
                                approved = True
                            else:
                                approved = loop.run_until_complete(self._request_plan_approval(plan))
                        except RuntimeError:
                            approved = True  # No event loop, auto-approve
                    else:
                        approved = True  # No callback, auto-approve

                    if not approved:
                        console.print("[bold red]Plan rejected by user.[/bold red]")
                        final_response = "Plan rejected by user. Please provide feedback or a new request."
                        break

                    console.print("[bold green]Plan approved. Executing...[/bold green]")

                # Execute tools
                for tc in tool_calls:
                    name = tc["function"]["name"]
                    try:
                        args = json.loads(tc["function"]["arguments"])
                    except json.JSONDecodeError:
                        args = {}

                    console.print(f"\n[bold cyan]🛠️ Executing Tool:[/bold cyan] [yellow]{name}[/yellow]({args})")

                    # Check for diff approval (write_file, edit_file)
                    needs_diff_approval = (
                        not self.accept_edits and
                        name in ("write_file", "edit_file")
                    )

                    # Check if we need permission approval (skip in DONT_ASK and BYPASS_PERMISSIONS modes)
                    needs_permission_approval = (
                        self._should_check_permissions() and
                        is_destructive_tool(name, args)
                    )

                    # Check if we need safety check (skip in BYPASS_PERMISSIONS mode)
                    needs_safety_check = (
                        self._should_check_safety() and
                        name == "bash" and
                        is_destructive_bash(args.get("command", ""))
                    )

                    # Handle permission approval for destructive tools
                    if needs_permission_approval:
                        console.print(f"\n[bold yellow]⚠ Permission Required:[/bold yellow] {name} is potentially destructive")
                        if not Confirm.ask("[bold yellow]Allow execution?[/bold yellow]"):
                            observation = "Tool execution rejected by user."
                            console.print("[bold red]Execution rejected.[/bold red]")
                            executed_tools.append({"name": name, "args": args, "obs": observation})
                            self.messages.append({
                                "role": "tool",
                                "tool_call_id": tc["id"],
                                "content": observation
                            })
                            continue

                    # Handle safety check for destructive bash commands
                    if needs_safety_check:
                        console.print(f"\n[bold red]⚠ Safety Alert:[/bold red] Destructive command detected: [yellow]{args.get('command', '')}[/yellow]")
                        if not Confirm.ask("[bold red]Allow execution?[/bold red]"):
                            observation = "Command blocked by user."
                            console.print("[bold red]Command blocked.[/bold red]")
                            executed_tools.append({"name": name, "args": args, "obs": observation})
                            self.messages.append({
                                "role": "tool",
                                "tool_call_id": tc["id"],
                                "content": observation
                            })
                            continue

                    if needs_diff_approval and name == "write_file":
                        path = args.get("path", "")
                        new_content = args.get("content", "")
                        try:
                            old_content = Path(path).expanduser().resolve().read_text()
                        except Exception:
                            old_content = ""

                        approved = True
                        if self.diff_approval_callback:
                            import asyncio
                            try:
                                loop = asyncio.get_event_loop()
                                if not loop.is_running():
                                    approved = loop.run_until_complete(
                                        self._request_diff_approval(path, old_content, new_content)
                                    )
                            except RuntimeError:
                                pass

                        if not approved:
                            observation = "File write rejected by user."
                            console.print("[bold red]File write rejected.[/bold red]")
                        else:
                            observation = self._execute_tool(name, args)

                    elif needs_diff_approval and name == "edit_file":
                        path = args.get("path", "")
                        old_str = args.get("old_str", "")
                        new_str = args.get("new_str", "")

                        try:
                            full_content = Path(path).expanduser().resolve().read_text()
                            if old_str in full_content:
                                new_content = full_content.replace(old_str, new_str)
                            else:
                                new_content = full_content
                        except Exception:
                            new_content = ""

                        approved = True
                        if self.diff_approval_callback:
                            import asyncio
                            try:
                                loop = asyncio.get_event_loop()
                                if not loop.is_running():
                                    approved = loop.run_until_complete(
                                        self._request_diff_approval(path, full_content, new_content)
                                    )
                            except RuntimeError:
                                pass

                        if not approved:
                            observation = "File edit rejected by user."
                            console.print("[bold red]File edit rejected.[/bold red]")
                        else:
                            observation = self._execute_tool(name, args)
                    else:
                        observation = self._execute_tool(name, args)

                    executed_tools.append({"name": name, "args": args, "obs": observation})
                    ui_obs = observation[:500] + "..." if len(observation) > 500 else observation
                    console.print(f"[dim]Observation: {ui_obs}[/dim]")

                    self.messages.append({
                        "role": "tool",
                        "tool_call_id": tc["id"],
                        "content": observation
                    })

                # --- NVIDIA FREE-TIER COOLDOWN ---
                time.sleep(1.5)
            else:
                final_response = content
                break

        # --- PHASE 3: POST-EXECUTION CACHE SAVE ---
        if final_response:
            save_to_cache(user_input, final_response, executed_tools)