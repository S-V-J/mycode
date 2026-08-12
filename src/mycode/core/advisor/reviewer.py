"""Advisor Model - Secondary model reviews primary output."""
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from enum import Enum


class ReviewSeverity(str, Enum):
    """Severity level for review findings."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


@dataclass
class ReviewFinding:
    """A single review finding."""
    severity: ReviewSeverity
    category: str  # "security", "performance", "style", "correctness", "maintainability"
    message: str
    suggestion: str
    line: Optional[int] = None

    def to_dict(self) -> dict:
        return {
            "severity": self.severity.value,
            "category": self.category,
            "message": self.message,
            "suggestion": self.suggestion,
            "line": self.line,
        }


@dataclass
class ReviewResult:
    """Result of an advisor review."""
    approved: bool
    findings: List[ReviewFinding] = field(default_factory=list)
    summary: str = ""
    overall_score: float = 0.0  # 0.0 to 1.0

    def to_dict(self) -> dict:
        return {
            "approved": self.approved,
            "findings": [f.to_dict() for f in self.findings],
            "summary": self.summary,
            "overall_score": self.overall_score,
        }


class AdvisorReviewer:
    """Advisor model for reviewing primary model output."""

    def __init__(self, client=None):
        self.client = client
        self.critical_threshold = 0.3  # Block if >30% critical findings
        self.score_threshold = 0.6     # Block if score < 0.6

    def review_code(
        self,
        original_prompt: str,
        response: str,
        language: str = "python",
        context: Optional[str] = None,
    ) -> ReviewResult:
        """Review AI-generated code response."""
        findings = []

        # Static analysis checks
        findings.extend(self._check_security_patterns(response))
        findings.extend(self._check_style_issues(response, language))
        findings.extend(self._check_completeness(response, original_prompt))

        # Calculate score
        critical_count = sum(1 for f in findings if f.severity == ReviewSeverity.CRITICAL)
        high_count = sum(1 for f in findings if f.severity == ReviewSeverity.HIGH)
        total = len(findings) if findings else 1

        # Score: penalize critical/high findings
        penalty = (critical_count * 0.3 + high_count * 0.1) / total
        score = max(0.0, min(1.0, 1.0 - penalty))

        approved = (
            critical_count == 0
            and score >= self.score_threshold
        )

        summary = self._generate_summary(findings, score)

        return ReviewResult(
            approved=approved,
            findings=findings,
            summary=summary,
            overall_score=score,
        )

    def _check_security_patterns(self, code: str) -> List[ReviewFinding]:
        """Check for common security anti-patterns."""
        findings = []
        lines = code.split("\n")

        dangerous_patterns = [
            ("eval(", "Avoid eval() - code injection risk"),
            ("exec(", "Avoid exec() - code injection risk"),
            ("os.system(", "Use subprocess instead of os.system"),
            ("subprocess.call(shell=True", "Avoid shell=True in subprocess"),
            ("pickle.loads", "Avoid pickle.loads - deserialization risk"),
            ("yaml.load(", "Use yaml.safe_load() instead of yaml.load()"),
            ("random.", "Consider secrets module for cryptographic use"),
        ]

        for pattern, message in dangerous_patterns:
            for i, line in enumerate(lines, 1):
                if pattern in line and not line.strip().startswith("#"):
                    findings.append(ReviewFinding(
                        severity=ReviewSeverity.HIGH,
                        category="security",
                        message=message,
                        suggestion=f"Line {i}: Replace with safe alternative",
                        line=i,
                    ))

        return findings

    def _check_style_issues(self, code: str, language: str) -> List[ReviewFinding]:
        """Check for style issues."""
        findings = []
        lines = code.split("\n")

        for i, line in enumerate(lines, 1):
            if len(line) > 120:
                findings.append(ReviewFinding(
                    severity=ReviewSeverity.LOW,
                    category="style",
                    message=f"Line {i} exceeds 120 characters ({len(line)})",
                    suggestion="Consider breaking into multiple lines",
                    line=i,
                ))

            if language == "python":
                if line.strip().startswith("import *"):
                    findings.append(ReviewFinding(
                        severity=ReviewSeverity.MEDIUM,
                        category="style",
                        message=f"Line {i}: Wildcard import",
                        suggestion="Import specific names instead of *",
                        line=i,
                    ))

        return findings

    def _check_completeness(self, response: str, prompt: str) -> List[ReviewFinding]:
        """Check if response addresses the prompt."""
        findings = []

        # Check for common incompleteness indicators
        if "..." in response or "TODO" in response or "FIXME" in response:
            findings.append(ReviewFinding(
                severity=ReviewSeverity.MEDIUM,
                category="correctness",
                message="Response contains incomplete markers (..., TODO, FIXME)",
                suggestion="Complete the implementation",
            ))

        if not response.strip():
            findings.append(ReviewFinding(
                severity=ReviewSeverity.CRITICAL,
                category="correctness",
                message="Response is empty",
                suggestion="Generate a complete response",
            ))

        return findings

    def _generate_summary(self, findings: List[ReviewFinding], score: float) -> str:
        """Generate review summary."""
        if not findings:
            return f"✓ Code review passed (score: {score:.2f})"

        by_severity = {}
        for f in findings:
            by_severity[f.severity.value] = by_severity.get(f.severity.value, 0) + 1

        parts = [f"{k}: {v}" for k, v in sorted(by_severity.items())]
        return f"Review score: {score:.2f}. Findings: {', '.join(parts)}"
