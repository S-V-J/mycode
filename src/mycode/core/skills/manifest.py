"""Skill manifest validation and schema definitions."""

import json
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Union
from pathlib import Path
from enum import Enum


class SkillArgumentType(str, Enum):
    """Types of skill arguments."""
    STRING = "string"
    INTEGER = "integer"
    NUMBER = "number"
    BOOLEAN = "boolean"
    ARRAY = "array"
    OBJECT = "object"
    FILE = "file"
    DIRECTORY = "directory"
    CHOICE = "choice"


@dataclass
class SkillArgument:
    """Skill argument definition."""
    name: str
    type: SkillArgumentType = SkillArgumentType.STRING
    description: str = ""
    required: bool = False
    default: Any = None
    choices: List[Any] = field(default_factory=list)
    min_value: Optional[Union[int, float]] = None
    max_value: Optional[Union[int, float]] = None
    pattern: str = ""
    items: Optional["SkillArgument"] = None  # For array type
    properties: Dict[str, "SkillArgument"] = field(default_factory=dict)  # For object type

    def validate(self, value: Any) -> List[str]:
        """Validate a value against this argument definition."""
        errors = []

        if value is None:
            if self.required:
                errors.append(f"Required argument '{self.name}' is missing")
            return errors

        # Type validation
        if self.type == SkillArgumentType.STRING:
            if not isinstance(value, str):
                errors.append(f"Argument '{self.name}' must be a string")
            elif self.pattern and not re.match(self.pattern, value):
                errors.append(f"Argument '{self.name}' does not match pattern: {self.pattern}")

        elif self.type == SkillArgumentType.INTEGER:
            if not isinstance(value, int) or isinstance(value, bool):
                errors.append(f"Argument '{self.name}' must be an integer")
            elif self.min_value is not None and value < self.min_value:
                errors.append(f"Argument '{self.name}' must be >= {self.min_value}")
            elif self.max_value is not None and value > self.max_value:
                errors.append(f"Argument '{self.name}' must be <= {self.max_value}")

        elif self.type == SkillArgumentType.NUMBER:
            if not isinstance(value, (int, float)) or isinstance(value, bool):
                errors.append(f"Argument '{self.name}' must be a number")
            elif self.min_value is not None and value < self.min_value:
                errors.append(f"Argument '{self.name}' must be >= {self.min_value}")
            elif self.max_value is not None and value > self.max_value:
                errors.append(f"Argument '{self.name}' must be <= {self.max_value}")

        elif self.type == SkillArgumentType.BOOLEAN:
            if not isinstance(value, bool):
                errors.append(f"Argument '{self.name}' must be a boolean")

        elif self.type == SkillArgumentType.ARRAY:
            if not isinstance(value, list):
                errors.append(f"Argument '{self.name}' must be an array")
            elif self.items:
                for i, item in enumerate(value):
                    item_errors = self.items.validate(item)
                    errors.extend([f"Argument '{self.name}[{i}]': {e}" for e in item_errors])

        elif self.type == SkillArgumentType.OBJECT:
            if not isinstance(value, dict):
                errors.append(f"Argument '{self.name}' must be an object")
            else:
                # Check required properties
                for prop_name, prop_def in self.properties.items():
                    prop_errors = prop_def.validate(value.get(prop_name))
                    errors.extend([f"Argument '{self.name}.{prop_name}': {e}" for e in prop_errors])
                # Check for unexpected properties
                for prop_name in value:
                    if prop_name not in self.properties:
                        errors.append(f"Argument '{self.name}' has unexpected property: {prop_name}")

        elif self.type == SkillArgumentType.CHOICE:
            if value not in self.choices:
                errors.append(f"Argument '{self.name}' must be one of: {self.choices}")

        elif self.type in (SkillArgumentType.FILE, SkillArgumentType.DIRECTORY):
            if not isinstance(value, str):
                errors.append(f"Argument '{self.name}' must be a path string")
            else:
                path = Path(value).expanduser()
                if self.type == SkillArgumentType.FILE and not path.is_file():
                    errors.append(f"File not found: {value}")
                elif self.type == SkillArgumentType.DIRECTORY and not path.is_dir():
                    errors.append(f"Directory not found: {value}")

        return errors

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        data = {
            "name": self.name,
            "type": self.type.value,
            "description": self.description,
            "required": self.required,
            "default": self.default,
        }
        if self.choices:
            data["choices"] = self.choices
        if self.min_value is not None:
            data["min_value"] = self.min_value
        if self.max_value is not None:
            data["max_value"] = self.max_value
        if self.pattern:
            data["pattern"] = self.pattern
        if self.items:
            data["items"] = self.items.to_dict()
        if self.properties:
            data["properties"] = {k: v.to_dict() for k, v in self.properties.items()}
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SkillArgument":
        """Create from dictionary."""
        items = None
        if "items" in data and data["items"]:
            items = cls.from_dict(data["items"])

        properties = {}
        for k, v in data.get("properties", {}).items():
            properties[k] = cls.from_dict(v)

        return cls(
            name=data["name"],
            type=SkillArgumentType(data.get("type", "string")),
            description=data.get("description", ""),
            required=data.get("required", False),
            default=data.get("default"),
            choices=data.get("choices", []),
            min_value=data.get("min_value"),
            max_value=data.get("max_value"),
            pattern=data.get("pattern", ""),
            items=items,
            properties=properties,
        )


@dataclass
class SkillManifest:
    """Skill manifest with metadata and arguments."""
    name: str
    version: str
    description: str
    author: str = ""
    license: str = "MIT"
    homepage: str = ""
    repository: str = ""
    keywords: List[str] = field(default_factory=list)

    # Skill definition
    command: str = ""  # The slash command name (e.g., "my-skill")
    entry_point: str = ""  # Module.ClassName or function path

    # Arguments
    arguments: List[SkillArgument] = field(default_factory=list)

    # Subagent integration
    spawns_subagents: bool = False
    subagent_prompts: List[str] = field(default_factory=list)

    # Requirements
    python_version: str = ">=3.10"
    mycode_version: str = ">=0.5.0"
    permissions: List[str] = field(default_factory=list)

    # Configuration
    config_schema: Optional[Dict[str, Any]] = None
    default_config: Dict[str, Any] = field(default_factory=dict)

    def validate(self) -> List[str]:
        """Validate manifest and return list of errors."""
        errors = []

        # Name validation
        if not self.name:
            errors.append("Name is required")
        elif not re.match(r'^[a-z0-9][a-z0-9_-]*$', self.name):
            errors.append("Name must be lowercase alphanumeric with underscores or hyphens")

        # Version validation (simple semver check)
        if not self.version:
            errors.append("Version is required")
        elif not re.match(r'^\d+\.\d+\.\d+', self.version):
            errors.append(f"Invalid version format: {self.version} (expected semver)")

        # Description validation
        if not self.description:
            errors.append("Description is required")

        # Command validation
        if not self.command:
            errors.append("Command is required")
        elif not re.match(r'^[a-z0-9][a-z0-9_-]*$', self.command):
            errors.append("Command must be lowercase alphanumeric with underscores or hyphens")

        # Entry point validation
        if not self.entry_point:
            errors.append("Entry point is required")

        # Argument validation
        arg_names = set()
        for arg in self.arguments:
            if arg.name in arg_names:
                errors.append(f"Duplicate argument name: {arg.name}")
            arg_names.add(arg.name)
            # Validate default value
            if arg.default is not None:
                default_errors = arg.validate(arg.default)
                if default_errors:
                    errors.extend([f"Default value for '{arg.name}': {e}" for e in default_errors])

        return errors

    def get_argument(self, name: str) -> Optional[SkillArgument]:
        """Get argument by name."""
        for arg in self.arguments:
            if arg.name == name:
                return arg
        return None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "author": self.author,
            "license": self.license,
            "homepage": self.homepage,
            "repository": self.repository,
            "keywords": self.keywords,
            "command": self.command,
            "entry_point": self.entry_point,
            "arguments": [arg.to_dict() for arg in self.arguments],
            "spawns_subagents": self.spawns_subagents,
            "subagent_prompts": self.subagent_prompts,
            "python_version": self.python_version,
            "mycode_version": self.mycode_version,
            "permissions": self.permissions,
            "config_schema": self.config_schema,
            "default_config": self.default_config,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SkillManifest":
        """Create manifest from dictionary."""
        arguments = [
            SkillArgument.from_dict(arg)
            for arg in data.get("arguments", [])
        ]
        return cls(
            name=data["name"],
            version=data["version"],
            description=data["description"],
            author=data.get("author", ""),
            license=data.get("license", "MIT"),
            homepage=data.get("homepage", ""),
            repository=data.get("repository", ""),
            keywords=data.get("keywords", []),
            command=data["command"],
            entry_point=data["entry_point"],
            arguments=arguments,
            spawns_subagents=data.get("spawns_subagents", False),
            subagent_prompts=data.get("subagent_prompts", []),
            python_version=data.get("python_version", ">=3.10"),
            mycode_version=data.get("mycode_version", ">=0.5.0"),
            permissions=data.get("permissions", []),
            config_schema=data.get("config_schema"),
            default_config=data.get("default_config", {}),
        )

    @classmethod
    def from_file(cls, path: Path) -> "SkillManifest":
        """Load manifest from skill.md or skill.json file."""
        if path.suffix == ".md":
            return cls.from_markdown(path)
        else:
            with open(path, 'r') as f:
                data = json.load(f)
            return cls.from_dict(data)

    @classmethod
    def from_markdown(cls, path: Path) -> "SkillManifest":
        """Load manifest from skill.md file with frontmatter."""
        content = path.read_text()

        # Parse frontmatter
        if content.startswith("---"):
            parts = content.split("---", 2)
            if len(parts) >= 3:
                import yaml
                frontmatter = yaml.safe_load(parts[1])
                return cls.from_dict(frontmatter)

        raise ValueError(f"No valid frontmatter found in {path}")

    def to_file(self, path: Path):
        """Save manifest to skill.json file."""
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, 'w') as f:
            json.dump(self.to_dict(), f, indent=2)

    def to_markdown(self, path: Path):
        """Save manifest to skill.md file with frontmatter."""
        path.parent.mkdir(parents=True, exist_ok=True)
        import yaml
        frontmatter = yaml.dump(self.to_dict(), sort_keys=False)
        content = f"---\n{frontmatter}---\n\n# {self.name}\n\n{self.description}\n"
        path.write_text(content)