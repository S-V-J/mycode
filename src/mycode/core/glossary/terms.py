"""Built-in glossary of AI/development terminology."""
from dataclasses import dataclass, field
from typing import List, Dict, Optional


@dataclass
class Term:
    """A glossary term."""
    term: str
    definition: str
    category: str = "general"
    related: List[str] = field(default_factory=list)


BUILTIN_TERMS = [
    Term("ReAct", "Reasoning + Acting pattern where AI thinks, acts, observes, and iterates", "ai",
         ["agent", "tool use", "reasoning"]),
    Term("Agent", "An AI system that can perceive and act in an environment to achieve goals", "ai",
         ["tool", "autonomous"]),
    Term("RAG", "Retrieval-Augmented Generation: enhancing LLM responses with retrieved context", "ai",
         ["vector database", "embedding"]),
    Term("Embedding", "Dense vector representation of text for semantic similarity", "ml",
         ["vector", "semantic"]),
    Term("Semantic Cache", "Cache keyed by meaning (embeddings) rather than exact text", "architecture",
         ["cache", "embedding"]),
    Term("Tree-sitter", "Incremental parsing library for source code", "tools",
         ["AST", "code parsing"]),
    Term("MCP", "Model Context Protocol: standard for connecting AI to external tools", "protocols",
         ["tool", "server"]),
    Term("Tool Use", "LLM capability to call external functions/APIs", "ai",
         ["function calling", "agent"]),
    Term("Context Window", "Maximum tokens an LLM can process in one request", "ai",
         ["token", "prompt"]),
    Term("Token", "Basic unit of text processing in LLMs (sub-word)", "ai",
         ["context window"]),
    Term("Diff", "Unified format showing changes between file versions", "tools",
         ["edit", "patch"]),
    Term("CWD", "Current Working Directory", "basics",
         ["path", "filesystem"]),
    Term("AEROPLANE Mode", "Offline mode using only cache + RAG, no API calls", "modes",
         ["offline", "cache"]),
    Term("PLAN Mode", "AI generates plan, user approves before execution", "modes",
         ["approval", "safety"]),
    Term("Prompt Caching", "Storing common prompt prefixes to reduce tokens/cost", "optimization",
         ["cache", "token"]),
    Term("Watchdog", "File system monitoring library for detecting changes", "tools",
         ["file watcher", "invalidation"]),
    Term("ChromaDB", "Open-source vector database for embeddings", "architecture",
         ["vector", "embedding", "cache"]),
    Term("Textual", "Python TUI framework by Textualize (built on Rich)", "tools",
         ["TUI", "Rich"]),
    Term("Typer", "Python CLI framework built on Click", "tools",
         ["CLI", "Click"]),
    Term("FastAPI", "Modern Python web framework for building APIs", "tools",
         ["web", "API"]),
]


class Glossary:
    """Searchable glossary of terms."""

    def __init__(self):
        self.terms: Dict[str, Term] = {t.term.lower(): t for t in BUILTIN_TERMS}

    def search(self, query: str) -> List[Term]:
        """Search terms by query string."""
        query = query.lower()
        results = []
        for term in self.terms.values():
            if (query in term.term.lower()
                or query in term.definition.lower()
                or query in term.category.lower()
                or any(query in r.lower() for r in term.related)):
                results.append(term)
        return results

    def get(self, term: str) -> Optional[Term]:
        return self.terms.get(term.lower())

    def get_by_category(self, category: str) -> List[Term]:
        return [t for t in self.terms.values() if t.category == category]

    def get_categories(self) -> List[str]:
        cats = set(t.category for t in self.terms.values())
        return sorted(cats)

    def add_term(self, term: Term):
        self.terms[term.term.lower()] = term


# Global instance
glossary = Glossary()
