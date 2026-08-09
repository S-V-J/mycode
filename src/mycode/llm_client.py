import json
from openai import OpenAI, APIError, RateLimitError, APIConnectionError, APIStatusError
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception
from rich.console import Console
from rich.markdown import Markdown

console = Console()

def is_nvidia_rate_limit(exception: Exception) -> bool:
    """Custom predicate to catch standard rate limits AND NVIDIA's specific Worker limit."""
    if isinstance(exception, (RateLimitError, APIConnectionError)):
        return True
    # NVIDIA returns ResourceExhausted as an APIStatusError (often 429 or 500)
    if isinstance(exception, APIStatusError):
        err_msg = str(exception)
        if "ResourceExhausted" in err_msg or "Worker local" in err_msg:
            return True
    return False

class NemotronClient:
    def __init__(self, api_key: str):
        self.client = OpenAI(
            base_url="https://integrate.api.nvidia.com/v1",
            api_key=api_key
        )
        self.model = "nvidia/nemotron-3-ultra-550b-a55b"

    @retry(
        stop=stop_after_attempt(5),
        # Increased wait times (4s, 8s, 16s) to allow NVIDIA's worker pool to reset
        wait=wait_exponential(multiplier=2, min=4, max=30),
        retry=retry_if_exception(is_nvidia_rate_limit),
        before_sleep=lambda retry_state: console.print(f"\n[yellow]⚠ NVIDIA API Concurrency Limit Hit. Retrying in {retry_state.next_action.sleep:.1f}s... (Attempt {retry_state.attempt_number}/5)[/yellow]")
    )
    def _create_stream(self, messages, tools):
        """Isolated API call to allow tenacity to retry on NVIDIA gateway limits."""
        kwargs = {
            "model": self.model,
            "messages": messages,
            "temperature":0.7,
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
            
        return self.client.chat.completions.create(**kwargs)

    def stream_chat(self, messages: list, tools: list = None) -> tuple[str, list]:
        """
        Streams chat completion with automatic exponential backoff for NVIDIA limits.
        """
        try:
            stream = self._create_stream(messages, tools)
        except Exception as e:
            console.print(f"\n[bold red]API Error after retries:[/bold red] {e}")
            return "", []

        is_thinking_active = False
        content_text = ""
        tool_calls_dict = {} 
        
        console.print("\n[dim italic]💭 Reasoning...[/dim italic]")
        
        try:
            for chunk in stream:
                if not chunk.choices: continue
                delta = chunk.choices[0].delta
                
                # 1. Handle Reasoning Stream
                reasoning = getattr(delta, "reasoning_content", None)
                if reasoning:
                    if not is_thinking_active:
                        is_thinking_active = True
                    console.print(reasoning, end="", style="dim", highlight=False)
                    continue
                    
                # 2. Transition to Content/Tools
                if is_thinking_active and (delta.content or delta.tool_calls):
                    console.print("\n")
                    is_thinking_active = False

                # 3. Accumulate standard content
                if delta.content:
                    content_text += delta.content
                    
                # 4. Accumulate Tool Call deltas
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
                            
        except Exception as e:
            # If the stream drops mid-generation due to a limit, we catch it gracefully.
            # The agent loop will naturally retry the step on the next iteration if needed.
            err_msg = str(e)
            if "ResourceExhausted" in err_msg or "Worker local" in err_msg:
                console.print(f"\n[yellow]⚠ Stream dropped due to NVIDIA concurrency limits. The agent will adapt.[/yellow]")
            else:
                console.print(f"\n[yellow]⚠ Stream interrupted mid-generation: {e}[/yellow]")

        final_tool_calls = list(tool_calls_dict.values())
        
        # Render final content as Markdown (Only if no tool calls were made)
        if content_text and not final_tool_calls:
            console.print() 
            console.print(Markdown(content_text))
            
        return content_text, final_tool_calls