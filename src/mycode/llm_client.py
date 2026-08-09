import json
from openai import OpenAI
from rich.console import Console
from rich.live import Live
from rich.markdown import Markdown

console = Console()

class NemotronClient:
    def __init__(self, api_key: str):
        self.client = OpenAI(
            base_url="https://integrate.api.nvidia.com/v1",
            api_key=api_key
        )
        self.model = "nvidia/nemotron-3-ultra-550b-a55b"

    def stream_chat(self, messages: list, tools: list = None) -> tuple[str, list]:
        """
        Streams chat completion. Fixes terminal duplication by strictly using Rich console.
        Returns: (final_text_content, tool_calls_list)
        """
        kwargs = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.7,
            "top_p": 0.95,
            "max_tokens": 4096,
            "stream": True,
            "extra_body": {
                "chat_template_kwargs": {"enable_thinking": True},
                "reasoning_budget": 4096
            }
        }
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"

        try:
            stream = self.client.chat.completions.create(**kwargs)
        except Exception as e:
            console.print(f"\n[bold red]API Error:[/bold red] {e}")
            return "", []

        is_thinking_active = False
        content_text = ""
        tool_calls_dict = {} 
        
        # Strictly use console.print to maintain perfect cursor tracking for Live updates
        console.print("\n[dim italic]💭 Reasoning...[/dim italic]")
        
        for chunk in stream:
            if not chunk.choices: continue
            delta = chunk.choices[0].delta
            
            # 1. Handle Reasoning Stream (Dim text, no markdown parsing)
            reasoning = getattr(delta, "reasoning_content", None)
            if reasoning:
                if not is_thinking_active:
                    is_thinking_active = True
                console.print(reasoning, end="", style="dim", highlight=False)
                continue
                
            # 2. Transition to Content/Tools
            if is_thinking_active and (delta.content or delta.tool_calls):
                console.print("\n") # Newline after reasoning block
                is_thinking_active = False

            # 3. Accumulate standard content
            if delta.content:
                content_text += delta.content
                
            # 4. Accumulate Tool Call deltas (OpenAI streams tool calls in chunks)
            if delta.tool_calls:
                for tc_delta in delta.tool_calls:
                    idx = tc_delta.index
                    if idx not in tool_calls_dict:
                        tool_calls_dict[idx] = {"id": "", "type": "function", "function": {"name": "", "arguments": ""}}
                    
                    if tc_delta.id:
                        tool_calls_dict[idx]["id"] = tc_delta.id
                    if tc_delta.function.name:
                        tool_calls_dict[idx]["function"]["name"] += tc_delta.function.name
                    if tc_delta.function.arguments:
                        tool_calls_dict[idx]["function"]["arguments"] += tc_delta.function.arguments

        # Finalize tool calls list
        final_tool_calls = list(tool_calls_dict.values())
        
        # Render final content as Markdown (Only if no tool calls were made)
        if content_text and not final_tool_calls:
            console.print() 
            console.print(Markdown(content_text))
            
        return content_text, final_tool_calls
