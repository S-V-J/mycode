"""Prompt Library - Curated templates for common coding tasks."""
from dataclasses import dataclass, field
from typing import Dict, List, Optional
import json
import os
from pathlib import Path

MYCODE_DIR = Path.home() / ".mycode"
PROMPTS_DIR = MYCODE_DIR / "prompts"
PROMPTS_DIR.mkdir(exist_ok=True)


@dataclass
class PromptTemplate:
    """A curated prompt template."""
    name: str
    description: str
    template: str
    category: str = "general"
    tags: List[str] = field(default_factory=list)
    args: Dict[str, str] = field(default_factory=dict)  # arg_name -> description

    def render(self, **kwargs) -> str:
        """Render template with provided arguments."""
        result = self.template
        for key, value in kwargs.items():
            result = result.replace(f"{{{{{key}}}}}", str(value))
        return result

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "template": self.template,
            "category": self.category,
            "tags": self.tags,
            "args": self.args,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "PromptTemplate":
        return cls(**data)


BUILTIN_PROMPTS = [
    PromptTemplate(
        name="refactor",
        description="Refactor code for readability and performance",
        category="refactoring",
        tags=["code", "cleanup", "optimize"],
        template="""Refactor the following code for better readability, performance, and maintainability.
Follow best practices for the language/framework being used.

Code to refactor:
```{language}
{code}
```

Requirements:
1. Improve naming and structure
2. Remove duplication (DRY principle)
3. Add type hints if applicable
4. Keep the same functionality
5. Explain key changes""",
        args={"language": "Programming language", "code": "Code to refactor"},
    ),
    PromptTemplate(
        name="debug",
        description="Debug an error or traceback",
        category="debugging",
        tags=["error", "bug", "traceback"],
        template="""Debug the following error. Analyze the traceback, identify the root cause, and provide a fix.

Error/Traceback:
```
{error}
```

Context (if any):
{context}

Please:
1. Explain what the error means
2. Identify the root cause
3. Provide the exact fix
4. Suggest how to prevent similar errors""",
        args={"error": "Error message or traceback", "context": "Additional context (optional)"},
    ),
    PromptTemplate(
        name="test",
        description="Generate unit tests for code",
        category="testing",
        tags=["test", "pytest", "unit"],
        template="""Generate comprehensive unit tests for the following code using {framework}.

Code to test:
```{language}
{code}
```

Requirements:
1. Cover happy paths
2. Cover edge cases
3. Cover error cases
4. Use appropriate mocking where needed
5. Follow {framework} best practices""",
        args={"framework": "Test framework (e.g., pytest, jest)", "language": "Language", "code": "Code to test"},
    ),
    PromptTemplate(
        name="review",
        description="Code review with suggestions",
        category="review",
        tags=["review", "quality", "suggestions"],
        template="""Perform a thorough code review of the following code.

```{language}
{code}
```

Review criteria:
1. Code correctness and potential bugs
2. Performance issues
3. Security vulnerabilities
4. Style and readability
5. Missing error handling
6. Documentation needs

Provide specific line-by-line suggestions with severity levels.""",
        args={"language": "Programming language", "code": "Code to review"},
    ),
    PromptTemplate(
        name="explain",
        description="Explain code in detail",
        category="documentation",
        tags=["explain", "document", "learn"],
        template="""Explain the following code in detail. Break down what each part does.

```{language}
{code}
```

Include:
1. Overall purpose and flow
2. Each function/class explanation
3. Key algorithms or patterns used
4. Any tricky or non-obvious parts""",
        args={"language": "Programming language", "code": "Code to explain"},
    ),
    PromptTemplate(
        name="security-audit",
        description="Security audit of code",
        category="security",
        tags=["security", "audit", "vulnerability"],
        template="""Perform a security audit of the following code. Look for common vulnerabilities.

```{language}
{code}
```

Check for:
1. Injection vulnerabilities (SQL, command, XSS)
2. Authentication/authorization issues
3. Data exposure risks
4. Cryptographic weaknesses
5. Insecure dependencies
6. Hardcoded secrets
7. Race conditions

Rate each finding by severity (Critical/High/Medium/Low).""",
        args={"language": "Programming language", "code": "Code to audit"},
    ),
    PromptTemplate(
        name="document",
        description="Generate documentation",
        category="documentation",
        tags=["docs", "readme", "docstring"],
        template="""Generate documentation for the following {doc_type}.

Content:
```{language}
{code}
```

Include:
1. Clear description of purpose
2. Parameters/arguments explained
3. Return values
4. Usage examples
5. Any important notes or warnings""",
        args={"doc_type": "Type of docs (docstring/README/API)", "language": "Language", "code": "Content"},
    ),
    PromptTemplate(
        name="migrate",
        description="Migrate code between versions/frameworks",
        category="migration",
        tags=["migrate", "upgrade", "version"],
        template="""Migrate the following code from {source} to {target}.

Original code:
```{language}
{code}
```

Requirements:
1. Maintain same functionality
2. Use {target} idioms and best practices
3. Highlight breaking changes
4. Provide migration notes""",
        args={"source": "Source framework/version", "target": "Target framework/version", "language": "Language", "code": "Code to migrate"},
    ),
]


class PromptLibrary:
    """Manage prompt templates."""

    def __init__(self):
        self.templates: Dict[str, PromptTemplate] = {}
        self._load_builtin()
        self._load_custom()

    def _load_builtin(self):
        """Load built-in templates."""
        for template in BUILTIN_PROMPTS:
            self.templates[template.name] = template

    def _load_custom(self):
        """Load custom templates from disk."""
        if PROMPTS_DIR.exists():
            for prompt_file in PROMPTS_DIR.glob("*.json"):
                try:
                    data = json.loads(prompt_file.read_text())
                    template = PromptTemplate.from_dict(data)
                    self.templates[template.name] = template
                except Exception:
                    pass

    def get(self, name: str) -> Optional[PromptTemplate]:
        return self.templates.get(name)

    def get_all(self) -> List[PromptTemplate]:
        return list(self.templates.values())

    def get_by_category(self, category: str) -> List[PromptTemplate]:
        return [t for t in self.templates.values() if t.category == category]

    def get_categories(self) -> List[str]:
        cats = set(t.category for t in self.templates.values())
        return sorted(cats)

    def search(self, query: str) -> List[PromptTemplate]:
        query = query.lower()
        return [
            t for t in self.templates.values()
            if query in t.name.lower()
            or query in t.description.lower()
            or any(query in tag for tag in t.tags)
        ]

    def add_custom(self, template: PromptTemplate) -> bool:
        self.templates[template.name] = template
        prompt_file = PROMPTS_DIR / f"{template.name}.json"
        try:
            prompt_file.write_text(json.dumps(template.to_dict(), indent=2))
            return True
        except Exception:
            return False

    def remove(self, name: str) -> bool:
        if name in self.templates:
            del self.templates[name]
            prompt_file = PROMPTS_DIR / f"{name}.json"
            try:
                prompt_file.unlink(missing_ok=True)
                return True
            except Exception:
                return False
        return False


# Global instance
prompt_library = PromptLibrary()
