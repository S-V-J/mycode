"""Skill evaluation and testing framework."""

import json
import asyncio
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Callable
from pathlib import Path
from enum import Enum
import traceback

from .manifest import SkillManifest, SkillArgument
from .registry import SkillRegistry, RegisteredSkill
from .executor import SkillExecutor, SkillResult, SkillContext, SkillEvalFramework


class TestSeverity(str, Enum):
    """Test severity levels."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


@dataclass
class SkillTestCase:
    """A single test case for a skill."""
    name: str
    description: str
    args: Dict[str, Any]
    expected_output: Any = None
    expected_error: str = None
    severity: TestSeverity = TestSeverity.MEDIUM
    timeout: float = 30.0
    setup: Optional[Callable] = None
    teardown: Optional[Callable] = None
    tags: List[str] = field(default_factory=list)


@dataclass
class SkillTestResult:
    """Result of a skill test case."""
    test_case: SkillTestCase
    passed: bool
    result: SkillResult
    duration: float
    error: str = ""


@dataclass
class SkillTestSuite:
    """Collection of test cases for a skill."""
    skill_name: str
    test_cases: List[SkillTestCase] = field(default_factory=list)
    setup: Optional[Callable] = None
    teardown: Optional[Callable] = None

    def add_test(self, test_case: SkillTestCase):
        """Add a test case to the suite."""
        self.test_cases.append(test_case)

    def add_test_simple(
        self,
        name: str,
        args: Dict[str, Any],
        expected_output: Any = None,
        expected_error: str = None,
        severity: TestSeverity = TestSeverity.MEDIUM
    ):
        """Add a simple test case."""
        self.add_test(SkillTestCase(
            name=name,
            description=name,
            args=args,
            expected_output=expected_output,
            expected_error=expected_error,
            severity=severity
        ))


class SkillEvaluator:
    """Evaluates skills against test suites."""

    def __init__(self, executor: SkillExecutor):
        self.executor = executor
        self.suites: Dict[str, SkillTestSuite] = {}

    def register_suite(self, suite: SkillTestSuite):
        """Register a test suite for a skill."""
        self.suites[suite.skill_name] = suite

    def create_suite(self, skill_name: str) -> SkillTestSuite:
        """Create a new test suite for a skill."""
        suite = SkillTestSuite(skill_name=skill_name)
        self.suites[skill_name] = suite
        return suite

    async def run_suite(self, skill_name: str, context: SkillContext = None) -> Dict[str, Any]:
        """Run all tests in a suite."""
        suite = self.suites.get(skill_name)
        if not suite:
            return {"error": f"No test suite for skill '{skill_name}'"}

        results = {
            "skill_name": skill_name,
            "total": len(suite.test_cases),
            "passed": 0,
            "failed": 0,
            "errors": 0,
            "duration": 0.0,
            "test_results": []
        }

        import time
        start_time = time.time()

        # Run suite setup
        if suite.setup:
            try:
                if asyncio.iscoroutinefunction(suite.setup):
                    await suite.setup()
                else:
                    suite.setup()
            except Exception as e:
                results["errors"] += 1
                results["test_results"].append({
                    "name": "suite_setup",
                    "passed": False,
                    "error": f"Suite setup failed: {e}"
                })

        # Run each test case
        for test_case in suite.test_cases:
            test_start = time.time()

            # Run test setup
            if test_case.setup:
                try:
                    if asyncio.iscoroutinefunction(test_case.setup):
                        await test_case.setup()
                    else:
                        test_case.setup()
                except Exception as e:
                    results["failed"] += 1
                    results["test_results"].append({
                        "name": test_case.name,
                        "passed": False,
                        "duration": time.time() - test_start,
                        "error": f"Test setup failed: {e}"
                    })
                    continue

            # Execute skill
            try:
                result = await asyncio.wait_for(
                    self.executor.execute_async(skill_name, test_case.args, context),
                    timeout=test_case.timeout
                )
            except asyncio.TimeoutError:
                result = SkillResult(success=False, error=f"Test timed out after {test_case.timeout}s")
            except Exception as e:
                result = SkillResult(success=False, error=f"Execution error: {e}")

            # Evaluate result
            passed = False
            error = ""

            if test_case.expected_error:
                passed = not result.success and test_case.expected_error in result.error
                if not passed:
                    error = f"Expected error '{test_case.expected_error}', got: {result.error or 'success'}"
            elif test_case.expected_output is not None:
                passed = result.success and self._compare_output(result.output, test_case.expected_output)
                if not passed:
                    error = f"Output mismatch. Expected: {test_case.expected_output}, Got: {result.output}"
            else:
                passed = result.success
                if not passed:
                    error = result.error

            test_duration = time.time() - test_start

            if passed:
                results["passed"] += 1
            else:
                results["failed"] += 1

            results["test_results"].append({
                "name": test_case.name,
                "description": test_case.description,
                "passed": passed,
                "duration": test_duration,
                "error": error,
                "severity": test_case.severity.value,
                "tags": test_case.tags,
                "output": result.output,
            })

            # Run test teardown
            if test_case.teardown:
                try:
                    if asyncio.iscoroutinefunction(test_case.teardown):
                        await test_case.teardown()
                    else:
                        test_case.teardown()
                except Exception:
                    pass  # Ignore teardown errors

        # Run suite teardown
        if suite.teardown:
            try:
                if asyncio.iscoroutinefunction(suite.teardown):
                    await suite.teardown()
                else:
                    suite.teardown()
            except Exception:
                pass

        results["duration"] = time.time() - start_time
        return results

    def _compare_output(self, actual: Any, expected: Any) -> bool:
        """Compare actual output with expected output."""
        if isinstance(expected, dict) and isinstance(actual, dict):
            # Partial match for dicts
            for key, value in expected.items():
                if key not in actual:
                    return False
                if not self._compare_output(actual[key], value):
                    return False
            return True
        elif isinstance(expected, list) and isinstance(actual, list):
            if len(expected) != len(actual):
                return False
            for a, e in zip(actual, expected):
                if not self._compare_output(a, e):
                    return False
            return True
        else:
            return actual == expected

    async def run_all_suites(self, context: SkillContext = None) -> Dict[str, Any]:
        """Run all registered test suites."""
        all_results = {}
        for skill_name in self.suites:
            all_results[skill_name] = await self.run_suite(skill_name, context)
        return all_results

    def generate_report(self, results: Dict[str, Any], format: str = "text") -> str:
        """Generate a test report."""
        if format == "json":
            return json.dumps(results, indent=2, default=str)

        # Text format
        lines = []
        lines.append("=" * 60)
        lines.append("SKILL TEST REPORT")
        lines.append("=" * 60)

        total_tests = 0
        total_passed = 0
        total_failed = 0
        total_errors = 0

        for skill_name, result in results.items():
            if "error" in result:
                lines.append(f"\n{skill_name}: ERROR - {result['error']}")
                continue

            lines.append(f"\n{skill_name}")
            lines.append("-" * 40)
            lines.append(f"  Total: {result['total']} | Passed: {result['passed']} | Failed: {result['failed']} | Errors: {result['errors']} | Duration: {result['duration']:.2f}s")

            total_tests += result['total']
            total_passed += result['passed']
            total_failed += result['failed']
            total_errors += result['errors']

            for test in result['test_results']:
                status = "✓" if test['passed'] else "✗"
                lines.append(f"  {status} {test['name']} ({test['duration']:.2f}s)")
                if not test['passed'] and test['error']:
                    lines.append(f"    Error: {test['error']}")

        lines.append("\n" + "=" * 60)
        lines.append(f"SUMMARY: {total_tests} tests, {total_passed} passed, {total_failed} failed, {total_errors} errors")
        lines.append("=" * 60)

        return "\n".join(lines)


class SkillCreator:
    """Helper for creating new skills interactively."""

    def __init__(self, registry: SkillRegistry):
        self.registry = registry

    def create_skill_interactive(self, output_dir: Path) -> bool:
        """Create a skill interactively (placeholder for CLI)."""
        # This would be used by a CLI command
        print("Skill Creator - Interactive Mode")
        print("This would prompt for skill details and generate a template.")
        return True

    def create_from_template(self, template_name: str, skill_name: str, output_dir: Path, **kwargs) -> bool:
        """Create a skill from a template."""
        templates = {
            "basic": self._basic_template,
            "file_processor": self._file_processor_template,
            "api_client": self._api_client_template,
            "subagent": self._subagent_template,
        }

        if template_name not in templates:
            print(f"Unknown template: {template_name}")
            return False

        return templates[template_name](skill_name, output_dir, **kwargs)

    def _basic_template(self, skill_name: str, output_dir: Path, **kwargs) -> bool:
        """Create a basic skill template."""
        from .manifest import SkillManifest, SkillArgument, SkillArgumentType

        output_dir.mkdir(parents=True, exist_ok=True)

        manifest = SkillManifest(
            name=skill_name,
            version="0.1.0",
            description=kwargs.get("description", f"{skill_name} skill"),
            author=kwargs.get("author", ""),
            command=skill_name.replace("_", "-"),
            entry_point=f"{skill_name}.main",
            arguments=[
                SkillArgument(
                    name="input",
                    type=SkillArgumentType.STRING,
                    description=kwargs.get("input_description", "Input parameter"),
                    required=kwargs.get("input_required", False)
                )
            ]
        )
        manifest.to_file(output_dir / "skill.json")

        # Main module
        main_py = output_dir / f"{skill_name}.py"
        main_py.write_text(f'''"""
{skill_name} skill implementation.
"""

from typing import Any, Dict
from pathlib import Path
from mycode.core.skills.executor import SkillContext, SkillResult


def main(context: SkillContext, input: str = "") -> SkillResult:
    """Main entry point for the skill."""
    # Your skill logic here
    return SkillResult(
        success=True,
        output={{"message": f"Hello from {skill_name}!", "input": input}}
    )


if __name__ == "__main__":
    import asyncio
    context = SkillContext(
        skill_name="{skill_name}",
        arguments={{}},
        config={{}},
        project_dir=Path.cwd(),
        config_dir=Path.home() / ".mycode"
    )
    result = main(context, input="test")
    print(result.output)
''')

        return True

    def _file_processor_template(self, skill_name: str, output_dir: Path, **kwargs) -> bool:
        """Create a file processor skill template."""
        from .manifest import SkillManifest, SkillArgument, SkillArgumentType

        output_dir.mkdir(parents=True, exist_ok=True)

        manifest = SkillManifest(
            name=skill_name,
            version="0.1.0",
            description=kwargs.get("description", f"Process files with {skill_name}"),
            author=kwargs.get("author", ""),
            command=skill_name.replace("_", "-"),
            entry_point=f"{skill_name}.main",
            arguments=[
                SkillArgument(
                    name="input_file",
                    type=SkillArgumentType.FILE,
                    description="Input file to process",
                    required=True
                ),
                SkillArgument(
                    name="output_file",
                    type=SkillArgumentType.STRING,
                    description="Output file path",
                    required=False
                ),
                SkillArgument(
                    name="format",
                    type=SkillArgumentType.CHOICE,
                    description="Output format",
                    choices=["json", "yaml", "text"],
                    default="json"
                )
            ],
            permissions=["file:read", "file:write"]
        )
        manifest.to_file(output_dir / "skill.json")

        main_py = output_dir / f"{skill_name}.py"
        main_py.write_text(f'''"""
{skill_name} - File processor skill.
"""

from typing import Any, Dict
from pathlib import Path
from mycode.core.skills.executor import SkillContext, SkillResult


def main(context: SkillContext, input_file: str, output_file: str = "", format: str = "json") -> SkillResult:
    """Process a file."""
    input_path = Path(input_file).expanduser()

    if not input_path.exists():
        return SkillResult(success=False, error=f"Input file not found: {{input_file}}")

    # Read input
    content = input_path.read_text()

    # Process (example: count lines, words, chars)
    lines = content.count('\\n') + 1
    words = len(content.split())
    chars = len(content)

    result_data = {{
        "file": str(input_path),
        "lines": lines,
        "words": words,
        "chars": chars,
        "format": format
    }}

    # Write output if specified
    if output_file:
        output_path = Path(output_file).expanduser()
        output_path.parent.mkdir(parents=True, exist_ok=True)

        if format == "json":
            import json
            output_path.write_text(json.dumps(result_data, indent=2))
        elif format == "yaml":
            import yaml
            output_path.write_text(yaml.dump(result_data))
        else:
            output_path.write_text(f"Lines: {{lines}}, Words: {{words}}, Chars: {{chars}}")

        result_data["output_file"] = str(output_path)

    return SkillResult(success=True, output=result_data)


if __name__ == "__main__":
    import asyncio
    context = SkillContext(
        skill_name="{skill_name}",
        arguments={{}},
        config={{}},
        project_dir=Path.cwd(),
        config_dir=Path.home() / ".mycode"
    )
    result = main(context, input_file=".", output_file="/tmp/test_output.json")
    print(result.output)
''')

        return True

    def _api_client_template(self, skill_name: str, output_dir: Path, **kwargs) -> bool:
        """Create an API client skill template."""
        from .manifest import SkillManifest, SkillArgument, SkillArgumentType

        output_dir.mkdir(parents=True, exist_ok=True)

        manifest = SkillManifest(
            name=skill_name,
            version="0.1.0",
            description=kwargs.get("description", f"API client for {skill_name}"),
            author=kwargs.get("author", ""),
            command=skill_name.replace("_", "-"),
            entry_point=f"{skill_name}.main",
            arguments=[
                SkillArgument(
                    name="endpoint",
                    type=SkillArgumentType.STRING,
                    description="API endpoint",
                    required=True
                ),
                SkillArgument(
                    name="method",
                    type=SkillArgumentType.CHOICE,
                    description="HTTP method",
                    choices=["GET", "POST", "PUT", "DELETE"],
                    default="GET"
                ),
                SkillArgument(
                    name="data",
                    type=SkillArgumentType.OBJECT,
                    description="Request body (for POST/PUT)",
                    required=False
                ),
                SkillArgument(
                    name="headers",
                    type=SkillArgumentType.OBJECT,
                    description="Request headers",
                    required=False
                )
            ],
            permissions=["network:http"]
        )
        manifest.to_file(output_dir / "skill.json")

        main_py = output_dir / f"{skill_name}.py"
        main_py.write_text(f'''"""
{skill_name} - API client skill.
"""

from typing import Any, Dict
from pathlib import Path
from mycode.core.skills.executor import SkillContext, SkillResult
import httpx


async def main(context: SkillContext, endpoint: str, method: str = "GET", data: Dict = None, headers: Dict = None) -> SkillResult:
    """Make an API request."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            request_headers = headers or {{}}
            request_headers.setdefault("User-Agent", "MyCode-Skill/{skill_name}")

            if method == "GET":
                response = await client.get(endpoint, headers=request_headers)
            elif method == "POST":
                response = await client.post(endpoint, json=data, headers=request_headers)
            elif method == "PUT":
                response = await client.put(endpoint, json=data, headers=request_headers)
            elif method == "DELETE":
                response = await client.delete(endpoint, headers=request_headers)
            else:
                return SkillResult(success=False, error=f"Unsupported method: {{method}}")

            return SkillResult(success=True, output={{
                "status_code": response.status_code,
                "headers": dict(response.headers),
                "body": response.text,
                "json": response.json() if response.headers.get("content-type", "").startswith("application/json") else None
            }})

        except httpx.TimeoutException:
            return SkillResult(success=False, error="Request timed out")
        except Exception as e:
            return SkillResult(success=False, error=f"Request failed: {{e}}")


if __name__ == "__main__":
    import asyncio
    context = SkillContext(
        skill_name="{skill_name}",
        arguments={{}},
        config={{}},
        project_dir=Path.cwd(),
        config_dir=Path.home() / ".mycode"
    )
    result = asyncio.run(main(context, endpoint="https://api.github.com/users/octocat"))
    print(result.output)
''')

        return True

    def _subagent_template(self, skill_name: str, output_dir: Path, **kwargs) -> bool:
        """Create a subagent skill template."""
        from .manifest import SkillManifest, SkillArgument, SkillArgumentType

        output_dir.mkdir(parents=True, exist_ok=True)

        manifest = SkillManifest(
            name=skill_name,
            version="0.1.0",
            description=kwargs.get("description", f"Subagent skill: {skill_name}"),
            author=kwargs.get("author", ""),
            command=skill_name.replace("_", "-"),
            entry_point=f"{skill_name}.main",
            arguments=[
                SkillArgument(
                    name="task",
                    type=SkillArgumentType.STRING,
                    description="Task for the subagent",
                    required=True
                ),
                SkillArgument(
                    name="model",
                    type=SkillArgumentType.CHOICE,
                    description="Model to use",
                    choices=["sonnet", "opus", "haiku", "fable"],
                    default="sonnet"
                )
            ],
            spawns_subagents=True,
            subagent_prompts=[
                "You are a specialized subagent. Complete the following task: {task}"
            ],
            permissions=["subagent:spawn"]
        )
        manifest.to_file(output_dir / "skill.json")

        main_py = output_dir / f"{skill_name}.py"
        main_py.write_text(f'''"""
{skill_name} - Subagent skill.
"""

from typing import Any, Dict
from pathlib import Path
from mycode.core.skills.executor import SkillContext, SkillResult


async def main(context: SkillContext, task: str, model: str = "sonnet") -> SkillResult:
    """Spawn a subagent to complete a task."""
    # This would integrate with the subagent system
    # For now, return a placeholder

    # Build the subagent prompt
    prompt = f"""You are a specialized subagent. Complete the following task:

{{task}}

Use the {model} model for this task.
"""

    return SkillResult(
        success=True,
        output={{
            "subagent_prompt": prompt,
            "model": model,
            "task": task
        }},
        metadata={{"mode": "subagent"}}
    )


if __name__ == "__main__":
    import asyncio
    context = SkillContext(
        skill_name="{skill_name}",
        arguments={{}},
        config={{}},
        project_dir=Path.cwd(),
        config_dir=Path.home() / ".mycode"
    )
    result = asyncio.run(main(context, task="Analyze the codebase for security issues"))
    print(result.output)
''')

        return True