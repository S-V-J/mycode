"""Skill registry for managing and discovering skills."""

import json
import asyncio
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Callable
from pathlib import Path
from enum import Enum
import importlib.util
import sys

from .manifest import SkillManifest, SkillArgument, SkillArgumentType


class SkillScope(str, Enum):
    """Skill installation scope."""
    USER = "user"
    PROJECT = "project"
    BUILTIN = "builtin"


@dataclass
class RegisteredSkill:
    """A registered skill with its manifest and loader."""
    manifest: SkillManifest
    scope: SkillScope
    path: Path
    module: Any = None
    entry_point: Callable = None
    config: Dict[str, Any] = field(default_factory=dict)
    enabled: bool = True
    error: str = ""


class SkillRegistry:
    """Registry for managing skills."""

    def __init__(self, config_dir: Path, project_dir: Optional[Path] = None):
        self.config_dir = config_dir
        self.project_dir = project_dir or Path.cwd()
        self.user_skills_dir = config_dir / "skills"
        self.project_skills_dir = self.project_dir / ".mycode" / "skills"
        self.builtin_skills_dir = Path(__file__).parent.parent / "skills" / "builtin"

        self.user_skills_dir.mkdir(parents=True, exist_ok=True)
        self.project_skills_dir.mkdir(parents=True, exist_ok=True)

        self.skills: Dict[str, RegisteredSkill] = {}
        self._load_skills()

    def _load_skills(self):
        """Load skills from all scopes."""
        # Load builtin skills
        if self.builtin_skills_dir.exists():
            for skill_dir in self.builtin_skills_dir.iterdir():
                if skill_dir.is_dir():
                    self._load_skill_from_dir(skill_dir, SkillScope.BUILTIN)

        # Load user skills
        for skill_dir in self.user_skills_dir.iterdir():
            if skill_dir.is_dir():
                self._load_skill_from_dir(skill_dir, SkillScope.USER)

        # Load project skills (override user/builtin)
        for skill_dir in self.project_skills_dir.iterdir():
            if skill_dir.is_dir():
                self._load_skill_from_dir(skill_dir, SkillScope.PROJECT)

    def _load_skill_from_dir(self, skill_dir: Path, scope: SkillScope):
        """Load a skill from its directory."""
        manifest_file = skill_dir / "skill.json"
        if not manifest_file.exists():
            # Try skill.md
            manifest_file = skill_dir / "skill.md"
            if not manifest_file.exists():
                return

        try:
            manifest = SkillManifest.from_file(manifest_file)

            # Check if already loaded (priority: project > user > builtin)
            if manifest.name in self.skills:
                existing = self.skills[manifest.name]
                if existing.scope.value >= scope.value:
                    return  # Skip lower priority

            # Load config
            config_file = skill_dir / "config.json"
            config = {}
            if config_file.exists():
                with open(config_file, 'r') as f:
                    config = json.load(f)

            enabled = config.get("enabled", True)

            # Load the skill module
            module = None
            entry_point = None
            error = ""

            if enabled:
                try:
                    module, entry_point = self._load_skill_module(skill_dir, manifest)
                except Exception as e:
                    error = str(e)
                    enabled = False

            skill = RegisteredSkill(
                manifest=manifest,
                scope=scope,
                path=skill_dir,
                module=module,
                entry_point=entry_point,
                config=config,
                enabled=enabled,
                error=error
            )
            self.skills[manifest.name] = skill

        except Exception as e:
            print(f"Warning: Failed to load skill from {skill_dir}: {e}")

    def _load_skill_module(self, skill_dir: Path, manifest: SkillManifest) -> tuple:
        """Load the skill's entry point module."""
        # Add skill directory to path
        skill_path_str = str(skill_dir)
        if skill_path_str not in sys.path:
            sys.path.insert(0, skill_path_str)

        # Parse entry point (e.g., "my_module.MyClass" or "my_module.my_function")
        entry_point_str = manifest.entry_point
        if "." not in entry_point_str:
            raise ValueError(f"Invalid entry point format: {entry_point_str}")

        module_name, class_or_function = entry_point_str.rsplit(".", 1)

        # Import module
        spec = importlib.util.find_spec(module_name)
        if spec is None:
            # Try relative to skill dir
            module_file = skill_dir / module_name.replace(".", "/")
            if module_file.with_suffix(".py").exists():
                spec = importlib.util.spec_from_file_location(module_name, module_file.with_suffix(".py"))
            elif (module_file / "__init__.py").exists():
                spec = importlib.util.spec_from_file_location(module_name, module_file / "__init__.py")

        if spec is None:
            raise ImportError(f"Module '{module_name}' not found in {skill_dir}")

        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        # Get the class or function
        entry_point = getattr(module, class_or_function)
        if entry_point is None:
            raise AttributeError(f"'{class_or_function}' not found in module '{module_name}'")

        return module, entry_point

    def register_skill(self, manifest: SkillManifest, scope: SkillScope = SkillScope.USER) -> bool:
        """Register a new skill."""
        if manifest.name in self.skills:
            existing = self.skills[manifest.name]
            if existing.scope.value >= scope.value:
                return False  # Higher or equal priority already exists

        # Create skill directory
        if scope == SkillScope.PROJECT:
            skill_dir = self.project_skills_dir / manifest.name
        else:
            skill_dir = self.user_skills_dir / manifest.name

        skill_dir.mkdir(parents=True, exist_ok=True)

        # Save manifest
        manifest.to_file(skill_dir / "skill.json")

        # Save default config
        config = {
            "enabled": True,
            "installed_at": "",
            "scope": scope.value,
        }
        import datetime
        config["installed_at"] = datetime.datetime.now().isoformat()
        with open(skill_dir / "config.json", 'w') as f:
            json.dump(config, f, indent=2)

        # Reload skills
        self._load_skills()
        return True

    def unregister_skill(self, name: str, scope: SkillScope = SkillScope.USER) -> bool:
        """Unregister a skill."""
        if name not in self.skills:
            return False

        skill = self.skills[name]
        if skill.scope != scope:
            return False  # Can only unregister from the same scope

        # Remove directory
        import shutil
        if skill.path.exists():
            shutil.rmtree(skill.path)

        # Remove from registry
        del self.skills[name]
        return True

    def enable_skill(self, name: str) -> bool:
        """Enable a skill."""
        if name not in self.skills:
            return False

        skill = self.skills[name]
        if skill.enabled:
            return True

        # Update config
        config = skill.config.copy()
        config["enabled"] = True
        with open(skill.path / "config.json", 'w') as f:
            json.dump(config, f, indent=2)

        # Reload
        try:
            module, entry_point = self._load_skill_module(skill.path, skill.manifest)
            skill.module = module
            skill.entry_point = entry_point
            skill.enabled = True
            skill.config = config
            skill.error = ""
            return True
        except Exception as e:
            skill.error = str(e)
            return False

    def disable_skill(self, name: str) -> bool:
        """Disable a skill."""
        if name not in self.skills:
            return False

        skill = self.skills[name]
        if not skill.enabled:
            return True

        # Update config
        config = skill.config.copy()
        config["enabled"] = False
        with open(skill.path / "config.json", 'w') as f:
            json.dump(config, f, indent=2)

        skill.enabled = False
        skill.config = config
        skill.module = None
        skill.entry_point = None
        return True

    def get_skill(self, name: str) -> Optional[RegisteredSkill]:
        """Get a skill by name."""
        return self.skills.get(name)

    def list_skills(self, scope: SkillScope = None, enabled_only: bool = False) -> List[RegisteredSkill]:
        """List all skills."""
        skills = list(self.skills.values())

        if scope:
            skills = [s for s in skills if s.scope == scope]

        if enabled_only:
            skills = [s for s in skills if s.enabled]

        return sorted(skills, key=lambda s: s.manifest.name)

    def get_skill_commands(self) -> Dict[str, RegisteredSkill]:
        """Get mapping of command names to skills."""
        commands = {}
        for skill in self.skills.values():
            if skill.enabled and skill.manifest.command:
                commands[skill.manifest.command] = skill
        return commands

    def validate_arguments(self, skill_name: str, args: Dict[str, Any]) -> List[str]:
        """Validate arguments for a skill."""
        skill = self.skills.get(skill_name)
        if not skill:
            return [f"Skill '{skill_name}' not found"]

        errors = []
        for arg_def in skill.manifest.arguments:
            value = args.get(arg_def.name)
            arg_errors = arg_def.validate(value)
            errors.extend(arg_errors)

        return errors