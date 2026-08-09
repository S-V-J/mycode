import json
from rich.console import Console
from .llm_client import NemotronClient
from .tools.schemas import TOOLS
from .tools.bash import execute_bash
from .tools.file_ops import read_file, write_file

console = Console()

class Agent:
    def __init__(self, client: NemotronClient):
        self.client = client
        self.messages = [
            {"role": "system", "content": "You are MyCode, an elite autonomous coding assistant. You have access to tools to interact with the local WSL system. Think step-by-step, use tools to gather information or make changes, and provide a final markdown response when done."}
        ]

    def run(self, user_input: str):
        self.messages.append({"role": "user", "content": user_input})
        
        # Max 5 iterations to prevent infinite loops
        for i in range(5):
            content, tool_calls = self.client.stream_chat(self.messages, tools=TOOLS)
            
            if tool_calls:
                # Append assistant message with tool calls
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
                
                # Execute tools and append observations
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
                        
                    # Truncate massive outputs for the terminal UI, but send full to LLM
                    ui_obs = observation[:500] + "..." if len(observation) > 500 else observation
                    console.print(f"[dim]Observation: {ui_obs}[/dim]") 
                    
                    self.messages.append({
                        "role": "tool",
                        "tool_call_id": tc["id"],
                        "content": observation
                    })
            else:
                # No tool calls, the agent is done and provided a final answer
                break
