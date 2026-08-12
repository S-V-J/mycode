"""Cost tracking for LLM API usage."""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Dict, List
from enum import Enum


class ProviderPricing(str, Enum):
    """Known pricing per 1M tokens (input/output in USD)."""
    NVIDIA_NEMOTRON_ULTRA = ("nvidia/nemotron-3-ultra", 0.0002, 0.0002)
    NVIDIA_NEMOTRON_4 = ("nvidia/nemotron-4-340b", 0.0001, 0.0002)
    GPT_4O = ("gpt-4o", 0.0025, 0.01)
    GPT_4O_MINI = ("gpt-4o-mini", 0.00015, 0.0006)
    CLAUDE_3_5_SONNET = ("anthropic/claude-3.5-sonnet", 0.003, 0.015)
    LLAMA_3_1_70B = ("meta-llama/llama-3.1-70b", 0.0009, 0.0009)

    def __init__(self, model_id: str, input_price: float, output_price: float):
        self.model_id = model_id
        self.input_price = input_price
        self.output_price = output_price


@dataclass
class CostEntry:
    """A single cost entry."""
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    model: str = ""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    input_cost: float = 0.0
    output_cost: float = 0.0
    total_cost: float = 0.0
    session_id: str = ""

    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp,
            "model": self.model,
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "input_cost": self.input_cost,
            "output_cost": self.output_cost,
            "total_cost": self.total_cost,
            "session_id": self.session_id,
        }


class CostTracker:
    """Track API costs."""

    PRICING: Dict[str, tuple] = {
        p.model_id: (p.input_price, p.output_price)
        for p in ProviderPricing
    }

    def __init__(self):
        self.entries: List[CostEntry] = []
        self._total_cost: float = 0.0
        self._total_tokens: int = 0
        self._by_model: Dict[str, float] = {}
        self._by_session: Dict[str, float] = {}

    def record(
        self,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
        session_id: str = "",
    ) -> CostEntry:
        """Record a cost entry."""
        input_price, output_price = self.PRICING.get(
            model, (0.0001, 0.0001)  # Default pricing
        )

        input_cost = (prompt_tokens / 1_000_000) * input_price
        output_cost = (completion_tokens / 1_000_000) * output_price
        total = input_cost + output_cost

        entry = CostEntry(
            model=model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            input_cost=input_cost,
            output_cost=output_cost,
            total_cost=total,
            session_id=session_id,
        )

        self.entries.append(entry)
        self._total_cost += total
        self._total_tokens += prompt_tokens + completion_tokens
        self._by_model[model] = self._by_model.get(model, 0.0) + total
        if session_id:
            self._by_session[session_id] = self._by_session.get(session_id, 0.0) + total

        return entry

    def get_total_cost(self) -> float:
        return self._total_cost

    def get_session_cost(self, session_id: str) -> float:
        return self._by_session.get(session_id, 0.0)

    def get_model_cost(self, model: str) -> float:
        return self._by_model.get(model, 0.0)

    def get_summary(self) -> Dict[str, Any]:
        return {
            "total_cost_usd": round(self._total_cost, 6),
            "total_tokens": self._total_tokens,
            "total_requests": len(self.entries),
            "by_model": {k: round(v, 6) for k, v in self._by_model.items()},
            "entries": [e.to_dict() for e in self.entries[-10:]],  # Last 10
        }


# Global instance
cost_tracker = CostTracker()
