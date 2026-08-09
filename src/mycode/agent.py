import json
from pathlib import Path
from rich.console import Console
from rich.markdown import Markdown
from .llm_client import NemotronClient
from .tools.schemas import TOOLS
from .tools.bash import execute_bash
from .tools.file_ops import read_file, write_file
from .cache import check_cache, save_to_cache
from .rag import retrieve_context
from .config import find_mycode_md

console = Console()

BASE_SYSTEM_PROMPT = "You are MyCode, an elite autonomous coding assistant. You have access to tools to interact with the local WSL system. Think step-by-step, use tools to gather information or make changes, and provide a final markdown response when done."

class Agent:
    def __init__(self, client: NemotronClient):
        self.client = client
        
        # --- PHASE 5: PROJECT MEMORY INJECTION ---
        project_rules = find_mycode_md(Path.cwd())
        
        self.base_prompt = BASE_SYSTEM_PROMPT
        if project_rules:
            self.base_prompt += f"\n\nPROJECT RULES & CONTEXT (from MYCODE.md):\n{project_rules}"
            
        self.messages = [
            {"role": "system", "content": self.base_prompt}
        ]

    def run(self, user_input: str):
        # --- PHASE 3: SEMANTIC CACHE INTERCEPTOR ---
        cached_result = check_cache(user_input)
        if cached_result:
            console.print(Markdown(cached_result["response"]))
            return

        # --- PHASE 4: AUTO-CONTEXT RAG INJECTION ---
        # Search the local codebase index for relevant chunks before asking the LLM
        rag_context = retrieve_context(user_input)
        if rag_context:
            self.messages[0]["content"] = self.base_prompt + "\n\n" + rag_context
        else:
            self.messages[0]["content"] = self.base_prompt

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
