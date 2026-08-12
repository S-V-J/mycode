"""Skill executor for running skills with argument parsing and subagent integration."""

import asyncio
import json
import inspect
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Callable, Union
from pathlib import Path
from enum import Enum
import traceback

from .manifest import SkillManifest, SkillArgument, SkillArgumentType
from .registry import SkillRegistry, RegisteredSkill, SkillScope


class SkillExecutionMode(str, Enum):
    """Skill execution modes."""
    SYNC = "sync"
    ASYNC = "async"
    SUBAGENT = "subagent"


@dataclass
class SkillResult:
    """Result of skill execution."""
    success: bool
    output: Any = None
    error: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SkillContext:
    """Context passed to skill execution."""
    skill_name: str
    arguments: Dict[str, Any]
    config: Dict[str, Any]
    project_dir: Path
    config_dir: Path
    # Runtime services
    mcp_client: Any = None
    plugin_manager: Any = None
    hook_registry: Any = None
    scheduler: Any = None


class SkillExecutor:
    """Executes skills with proper argument handling."""

    def __init__(self, registry: SkillRegistry, config_dir: Path, project_dir: Path):
        self.registry = registry
        self.config_dir = config_dir
        self.project_dir = project_dir
        self._subagents: Dict[str, Any] = {}  # For subagent integration

    def parse_arguments(self, skill_name: str, raw_args: List[str]) -> Dict[str, Any]:
        """Parse command-line arguments into skill arguments."""
        skill = self.registry.get_skill(skill_name)
        if not skill:
            raise ValueError(f"Skill '{skill_name}' not found")

        args = {}
        i = 0
        while i < len(raw_args):
            arg = raw_args[i]

            if arg.startswith("--"):
                # Long option
                name = arg[2:]
                if "=" in name:
                    name, value = name.split("=", 1)
                else:
                    # Check if next arg is a value
                    if i + 1 < len(raw_args) and not raw_args[i + 1].startswith("-"):
                        value = raw_args[i + 1]
                        i += 1
                    else:
                        value = True  # Boolean flag

                # Find argument definition
                arg_def = skill.manifest.get_argument(name)
                if arg_def:
                    args[name] = self._convert_value(value, arg_def)
                else:
                    args[name] = value

            elif arg.startswith("-") and len(arg) > 1:
                # Short options (e.g., -abc)
                for char in arg[1:]:
                    # Find argument with matching short name (first letter)
                    arg_def = next((a for a in skill.manifest.arguments if a.name.startswith(char)), None)
                    if arg_def:
                        if arg_def.type == SkillArgumentType.BOOLEAN:
                            args[arg_def.name] = True
                        else:
                            if i + 1 < len(raw_args):
                                i += 1
                                args[arg_def.name] = self._convert_value(raw_args[i], arg_def)
            else:
                # Positional argument
                # Find first required positional argument without a value
                positional_args = [a for a in skill.manifest.arguments if not a.name.startswith("_")]
                for arg_def in positional_args:
                    if arg_def.name not in args:
                        args[arg_def.name] = self._convert_value(arg, arg_def)
                        break

            i += 1

        # Apply defaults
        for arg_def in skill.manifest.arguments:
            if arg_def.name not in args and arg_def.default is not None:
                args[arg_def.name] = arg_def.default

        return args

    def _convert_value(self, value: str, arg_def: SkillArgument) -> Any:
        """Convert string value to argument type."""
        if arg_def.type == SkillArgumentType.STRING:
            return value
        elif arg_def.type == SkillArgumentType.INTEGER:
            return int(value)
        elif arg_def.type == SkillArgumentType.NUMBER:
            return float(value)
        elif arg_def.type == SkillArgumentType.BOOLEAN:
            return value.lower() in ("true", "1", "yes", "on")
        elif arg_def.type == SkillArgumentType.ARRAY:
            return json.loads(value) if value.startswith("[") else value.split(",")
        elif arg_def.type == SkillArgumentType.OBJECT:
            return json.loads(value)
        elif arg_def.type == SkillArgumentType.CHOICE:
            return value
        elif arg_def.type in (SkillArgumentType.FILE, SkillArgumentType.DIRECTORY):
            return value
        return value

    def validate_arguments(self, skill_name: str, args: Dict[str, Any]) -> List[str]:
        """Validate arguments for a skill."""
        return self.registry.validate_arguments(skill_name, args)

    def execute(self, skill_name: str, args: Dict[str, Any] = None, context: SkillContext = None) -> SkillResult:
        """Execute a skill synchronously."""
        if args is None:
            args = {}

        # Validate
        errors = self.validate_arguments(skill_name, args)
        if errors:
            return SkillResult(success=False, error="; ".join(errors))

        skill = self.registry.get_skill(skill_name)
        if not skill:
            return SkillResult(success=False, error=f"Skill '{skill_name}' not found")

        if not skill.enabled:
            return SkillResult(success=False, error=f"Skill '{skill_name}' is disabled")

        if not skill.entry_point:
            return SkillResult(success=False, error=f"Skill '{skill_name}' entry point not loaded")

        # Create context
        if context is None:
            context = SkillContext(
                skill_name=skill_name,
                arguments=args,
                config=skill.config,
                project_dir=self.project_dir,
                config_dir=self.config_dir
            )

        try:
            # Check if entry point is async
            if inspect.iscoroutinefunction(skill.entry_point):
                # Run async function
                return asyncio.run(self._execute_async(skill, args, context))
            else:
                # Run sync function
                result = skill.entry_point(context, **args)
                if inspect.iscoroutine(result):
                    result = asyncio.run(result)
                return SkillResult(success=True, output=result)

        except Exception as e:
            return SkillResult(success=False, error=f"{type(e).__name__}: {e}")

    async def _execute_async(self, skill: RegisteredSkill, args: Dict[str, Any], context: SkillContext) -> SkillResult:
        """Execute an async skill."""
        try:
            result = await skill.entry_point(context, **args)
            return SkillResult(success=True, output=result)
        except Exception as e:
            return SkillResult(success=False, error=f"{type(e).__name__}: {e}")

    async def execute_async(self, skill_name: str, args: Dict[str, Any] = None, context: SkillContext = None) -> SkillResult:
        """Execute a skill asynchronously."""
        if args is None:
            args = {}

        # Validate
        errors = self.validate_arguments(skill_name, args)
        if errors:
            return SkillResult(success=False, error="; ".join(errors))

        skill = self.registry.get_skill(skill_name)
        if not skill:
            return SkillResult(success=False, error=f"Skill '{skill_name}' not found")

        if not skill.enabled:
            return SkillResult(success=False, error=f"Skill '{skill_name}' is disabled")

        if not skill.entry_point:
            return SkillResult(success=False, error=f"Skill '{skill_name}' entry point not loaded")

        # Create context
        if context is None:
            context = SkillContext(
                skill_name=skill_name,
                arguments=args,
                config=skill.config,
                project_dir=self.project_dir,
                config_dir=self.config_dir
            )

        return await self._execute_async(skill, args, context)

    def execute_subagent(self, skill_name: str, args: Dict[str, Any] = None, prompt: str = None) -> SkillResult:
        """Execute a skill that spawns a subagent."""
        if args is None:
            args = {}

        skill = self.registry.get_skill(skill_name)
        if not skill:
            return SkillResult(success=False, error=f"Skill '{skill_name}' not found")

        if not skill.manifest.spawns_subagents:
            return SkillResult(success=False, error=f"Skill '{skill_name}' does not support subagents")

        # Build subagent prompt
        if prompt is None:
            subagent_prompts = skill.manifest.subagent_prompts
            if subagent_prompts:
                prompt = subagent_prompts[0]
            else:
                prompt = f"Execute skill {skill_name} with arguments: {args}"

        # Create context
        context = SkillContext(
            skill_name=skill_name,
            arguments=args,
            config=skill.config,
            project_dir=self.project_dir,
            config_dir=self.config_dir
        )

        # This would integrate with the subagent system
        # For now, return a placeholder
        return SkillResult(
            success=True,
            output={"subagent_prompt": prompt, "context": context.__dict__},
            metadata={"mode": "subagent"}
        )


class SkillEvalFramework:
    """Evaluation framework for testing skills."""

    def __init__(self, executor: SkillExecutor):
        self.executor = executor
        self.test_cases: Dict[str, List[Dict[str, Any]]] = {}

    def add_test_case(self, skill_name: str, args: Dict[str, Any], expected_output: Any = None, expected_error: str = None):
        """Add a test case for a skill."""
        if skill_name not in self.test_cases:
            self.test_cases[skill_name] = []
        self.test_cases[skill_name].append({
            "args": args,
            "expected_output": expected_output,
            "expected_error": expected_error,
        })

    def run_tests(self, skill_name: str) -> Dict[str, Any]:
        """Run all test cases for a skill."""
        if skill_name not in self.test_cases:
            return {"passed": 0, "failed": 0, "errors": ["No test cases found"]}

        results = {"passed": 0, "failed": 0, "details": []}

        for i, test_case in enumerate(self.test_cases[skill_name]):
            result = self.executor.execute(skill_name, test_case["args"])

            passed = False
            error = None

            if test_case["expected_error"]:
                passed = not result.success and test_case["expected_error"] in result.error
                if not passed:
                    error = f"Expected error '{test_case['expected_error']}', got: {result.error}"
            elif test_case["expected_output"] is not None:
                passed = result.success and result.output == test_case["expected_output"]
                if not passed:
                    error = f"Expected output {test_case['expected_output']}, got: {result.output}"
            else:
                passed = result.success
                if not passed:
                    error = result.error

            if passed:
                results["passed"] += 1
            else:
                results["failed"] += 1

            results["details"].append({
                "test": i,
                "passed": passed,
                "error": error,
                "output": result.output,
            })

        return results

    def run_all_tests(self) -> Dict[str, Any]:
        """Run tests for all skills with test cases."""
        all_results = {}
        for skill_name in self.test_cases:
            all_results[skill_name] = self.run_tests(skill_name)
        return all_results


class SkillSharing:
    """Export/import skill bundles."""

    def __init__(self, registry: SkillRegistry):
        self.registry = registry

    def export_skill(self, skill_name: str, output_path: Path) -> bool:
        """Export a skill as a bundle."""
        skill = self.registry.get_skill(skill_name)
        if not skill:
            return False

        import shutil
        import zipfile

        # Create bundle
        with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as zf:
            # Add all files from skill directory
            for file_path in skill.path.rglob("*"):
                if file_path.is_file():
                    arcname = file_path.relative_to(skill.path)
                    zf.write(file_path, arcname)

        return True

    def import_skill(self, bundle_path: Path, scope: SkillScope = SkillScope.USER) -> bool:
        """Import a skill from a bundle."""
        import zipfile
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            # Extract bundle
            with zipfile.ZipFile(bundle_path, 'r') as zf:
                zf.extractall(tmpdir_path)

            # Find skill manifest
            manifest_file = tmpdir_path / "skill.json"
            if not manifest_file.exists():
                manifest_file = tmpdir_path / "skill.md"
                if not manifest_file.exists():
                    return False

            # Load manifest
            from .manifest import SkillManifest
            manifest = SkillManifest.from_file(manifest_file)

            # Register skill
            return self.registry.register_skill(manifest, scope)

    def create_skill_template(self, name: str, output_dir: Path, skill_type: str = "basic") -> bool:
        """Create a skill template."""
        from .manifest import SkillManifest, SkillArgument, SkillArgumentType

        output_dir.mkdir(parents=True, exist_ok=True)

        # Create manifest
        manifest = SkillManifest(
            name=name,
            version="0.1.0",
            description=f"{name} skill",
            author="",
            command=name.replace("_", "-"),
            entry_point=f"{name}.main",
            arguments=[
                SkillArgument(
                    name="input",
                    type=SkillArgumentType.STRING,
                    description="Input parameter",
                    required=False
                )
            ]
        )

        # Save manifest
        manifest.to_file(output_dir / "skill.json")

        # Create main module
        main_py = output_dir / f"{name}.py"
        main_py.write_text(f'''"""
{name} skill implementation.
"""

from typing import Any, Dict
from pathlib import Path
from mycode.core.skills.executor import SkillContext, SkillResult


def main(context: SkillContext, input: str = "") -> SkillResult:
    """Main entry point for the skill."""
    # Your skill logic here
    return SkillResult(
        success=True,
        output={{"message": f"Hello from {name}!", "input": input}}
    )


if __name__ == "__main__":
    # For testing
    import asyncio
    context = SkillContext(
        skill_name="{name}",
        arguments={{}},
        config={{}},
        project_dir=Path.cwd(),
        config_dir=Path.home() / ".mycode"
    )
    result = main(context, input="test")
    print(result.output)
''')

        # Create README
        readme = output_dir / "README.md"
        readme.write_text(f'''# {name} Skill

{manifest.description}

## Installation

```bash
mycode skill install {name}
```

## Usage

```
/{manifest.command} --input "your input"
```

## Arguments

| Argument | Type | Required | Description |
|----------|------|----------|-------------|
| input    | string | No | Input parameter |

## Development

Edit `{name}.py` to implement your skill logic.
''')

        return True