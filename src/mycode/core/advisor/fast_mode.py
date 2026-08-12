"""Fast Mode - Route simple tasks to cheaper models."""
from dataclasses import dataclass
from enum import Enum
from typing import Optional, Dict, Any
import re


class ModelTier(str, Enum):
    """Model cost tiers."""
    FAST = "fast"          # Cheap, fast models for simple tasks
    STANDARD = "standard"  # Default models
    POWER = "power"        # Expensive models for complex tasks


@dataclass
class ComplexityScore:
    """Complexity analysis result."""
    score: float  # 0.0 (simple) to 1.0 (complex)
    tier: ModelTier
    reasons: list = field(default_factory=list)


class ComplexityAnalyzer:
    """Analyze prompt complexity to determine model routing."""

    COMPLEX_PATTERNS = [
        r"refactor",
        r"architecture",
        r"debug|traceback|error",
        r"security|vulnerability|exploit",
        r"optimize|performance|benchmark",
        r"entire|all files|multi-file|whole project",
        r"design pattern|best practice",
        r"analyze|investigate|why does|how does",
        r"implement.*from scratch",
        r"migrate|upgrade|breaking change",
    ]

    SIMPLE_PATTERNS = [
        r"^what (is|are)",
        r"^explain",
        r"^show me",
        r"^list",
        r"^find.*definition",
        r"^get.*value",
        r"^read.*file",
        r"^search.*for",
    ]

    def analyze(self, prompt: str, iteration: int = 0) -> ComplexityScore:
        """Analyze prompt complexity."""
        reasons = []
        score = 0.0
        prompt_lower = prompt.lower()

        # Length factor (0-0.3)
        length_factor = min(len(prompt) / 500, 1.0) * 0.3
        score += length_factor
        if len(prompt) > 300:
            reasons.append(f"Long prompt ({len(prompt)} chars)")

        # Keyword factors (0-0.4)
        for pattern in self.COMPLEX_PATTERNS:
            if re.search(pattern, prompt_lower):
                score += 0.05
                reasons.append(f"Complex keyword: {pattern}")

        # Simple patterns reduce score (0-0.2)
        for pattern in self.SIMPLE_PATTERNS:
            if re.search(pattern, prompt_lower):
                score -= 0.1
                reasons.append(f"Simple pattern: {pattern}")

        # Iteration factor (0-0.2)
        if iteration > 0:
            score += min(iteration * 0.05, 0.2)
            reasons.append(f"Deep iteration ({iteration})")

        # Clamp score
        score = max(0.0, min(1.0, score))

        # Determine tier
        if score < 0.3:
            tier = ModelTier.FAST
        elif score < 0.7:
            tier = ModelTier.STANDARD
        else:
            tier = ModelTier.POWER

        return ComplexityScore(score=score, tier=tier, reasons=reasons)


class FastModeRouter:
    """Route requests to appropriate model tier."""

    def __init__(self):
        self.analyzer = ComplexityAnalyzer()
        self.enabled = True
        self.fast_model = None   # Configured by user
        self.standard_model = None
        self.power_model = None

    def route(self, prompt: str, iteration: int = 0) -> Dict[str, Any]:
        """Determine which model tier to use."""
        if not self.enabled:
            return {"tier": ModelTier.STANDARD, "score": 0.5}

        analysis = self.analyzer.analyze(prompt, iteration)
        return {
            "tier": analysis.tier,
            "score": analysis.score,
            "reasons": analysis.reasons,
        }

    def get_params(self, tier: ModelTier) -> Dict[str, Any]:
        """Get model parameters for each tier."""
        params = {
            ModelTier.FAST: {
                "temperature": 0.1,
                "max_tokens": 2048,
                "reasoning_budget": 1024,
            },
            ModelTier.STANDARD: {
                "temperature": 0.2,
                "max_tokens": 4096,
                "reasoning_budget": 2048,
            },
            ModelTier.POWER: {
                "temperature": 1.0,
                "max_tokens": 16384,
                "reasoning_budget": 16384,
            },
        }
        return params.get(tier, params[ModelTier.STANDARD])
