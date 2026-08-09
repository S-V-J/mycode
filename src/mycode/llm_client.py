import sys
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

    def stream_chat(self, messages: list) -> str:
        """Streams chat completion using a Two-Phase Architecture to prevent terminal corruption."""
        
        try:
            stream = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.7,
                top_p=0.95,
                max_tokens=4096,
                stream=True,
                extra_body={
                    "chat_template_kwargs": {"enable_thinking": True},
                    "reasoning_budget": 4096
                }
            )
        except Exception as e:
            console.print(f"\n[bold red]API Error:[/bold red] {e}")
            return ""

        is_thinking_active = False
        content_text = ""
        
        # --- PHASE 1: Stream Reasoning (Raw stdout with ANSI codes) ---
        # We use raw stdout here because Rich's Live context manager will corrupt layout if mixed with raw writes.
        sys.stdout.write("\033[2m\033[3m") # ANSI: Dim + Italic for reasoning
        
        for chunk in stream:
            if not chunk.choices: continue
            delta = chunk.choices[0].delta
            
            # Extract Nemotron-specific reasoning delta
            reasoning = getattr(delta, "reasoning_content", None)
            if reasoning:
                is_thinking_active = True
                sys.stdout.write(reasoning)
                sys.stdout.flush()
                continue 
                
            # Detect transition to final content
            content = delta.content
            if content is not None:
                if is_thinking_active:
                    sys.stdout.write("\033[0m\n\n") # ANSI: Reset + Spacing
                    is_thinking_active = False
                
                content_text += content
                break # Break raw loop to hand control to Rich Live
                
        # Handle edge case where stream ends during reasoning
        if is_thinking_active:
            sys.stdout.write("\033[0m\n\n")
            
        # --- PHASE 2: Stream Content (Rich Live Markdown) ---
        # Now that reasoning is done, we use Rich to render the final markdown smoothly.
        with Live(Markdown(content_text), console=console, refresh_per_second=12, vertical_overflow="visible") as live:
            for chunk in stream:
                if not chunk.choices: continue
                delta = chunk.choices[0].delta
                
                content = delta.content
                if content is not None:
                    content_text += content
                    live.update(Markdown(content_text))
                    
        return content_text
