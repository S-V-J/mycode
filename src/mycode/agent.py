import json
import time
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
            
            content, tool_calls = self.client.stream_chat(self.messages, tools=TOOLS, params=params)
            
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
                    
                # --- NVIDIA FREE-TIER COOLDOWN ---
                time.sleep(1.5)
            else:
                final_response = content
                break

        # --- PHASE 3: POST-EXECUTION CACHE SAVE ---
        if final_response:
            save_to_cache(user_input, final_response, executed_tools)
