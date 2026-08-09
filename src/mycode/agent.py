import json
from rich.console import Console
from rich.markdown import Markdown
from .llm_client import NemotronClient
from .tools.schemas import TOOLS
from .tools.bash import execute_bash
from .tools.file_ops import read_file, write_file
from .cache import check_cache, save_to_cache

console = Console()

class Agent:
    def __init__(self, client: NemotronClient):
        self.client = client
        self.messages = [
            {"role": "system", "content": "You are MyCode, an elite autonomous coding assistant. You have access to tools to interact with the local WSL system. Think step-by-step, use tools to gather information or make changes, and provide a final markdown response when done."}
        ]

    def run(self, user_input: str):
        # --- PHASE 3: SEMANTIC CACHE INTERCEPTOR ---
        cached_result = check_cache(user_input)
        if cached_result:
            # Replay cached tool executions silently or just show the final answer
            # For safety, we will just print the cached final response to avoid re-running destructive bash commands
            console.print(Markdown(cached_result["response"]))
            return

        # --- STANDARD REACT LOOP (Cache Miss) ---
        self.messages.append({"role": "user", "content": user_input})
        final_response = ""
        executed_tools = []
        
        # Max 5 iterations to prevent infinite loops
        for i in range(5):
            content, tool_calls = self.client.stream_chat(self.messages, tools=TOOLS)
            
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
                
                for tc in tool_calls:
                    name = tc["function"]["name"]
                    try:
                        args = json.loads(tc["function"]["arguments"])
                    except json.JSONDecodeError:
                        args = {}
                        
                    console.print(f"\n[bold cyan]🛠️ Executing Tool:[/bold cyan] [yellow]{name}[/yellow]({args})")
                    
                    if name == "bash":
                        observation = execute_bash(args.get("command", ""))
                    elif name == "read_file":
                        observation = read_file(args.get("path", ""))
                    elif name == "write_file":
                        observation = write_file(args.get("path", ""), args.get("content", ""))
                    else:
                        observation = f"Error: Unknown tool {name}"
                        
                    executed_tools.append({"name": name, "args": args, "obs": observation})
                    ui_obs = observation[:500] + "..." if len(observation) > 500 else observation
                    console.print(f"[dim]Observation: {ui_obs}[/dim]") 
                    
                    self.messages.append({
                        "role": "tool",
                        "tool_call_id": tc["id"],
                        "content": observation
                    })
            else:
                final_response = content
                break

        # --- PHASE 3: POST-EXECUTION CACHE SAVE ---
        if final_response:
            save_to_cache(user_input, final_response, executed_tools)
