"""Skills system for MyCode - extensible command/skill architecture."""

from .manifest import (
    SkillManifest,
    SkillArgument,
    SkillArgumentType,
)

from .registry import (
    SkillRegistry,
    RegisteredSkill,
    SkillScope,
)

from .executor import (
    SkillExecutor,
    SkillResult,
    SkillContext,
    SkillExecutionMode,
    SkillEvalFramework,
    SkillSharing,
)

from .eval import (
    SkillEvaluator,
    SkillTestSuite,
    SkillTestCase,
    SkillTestResult,
    TestSeverity,
    SkillCreator,
)

# Global instances
_skill_registry = None
_skill_executor = None


def get_skill_registry(config_dir: Path, project_dir: Path = None) -> SkillRegistry:
    """Get or create the global skill registry."""
    global _skill_registry
    if _skill_registry is None:
        _skill_registry = SkillRegistry(config_dir, project_dir)
    return _skill_registry


def get_skill_executor(registry: SkillRegistry, config_dir: Path, project_dir: Path) -> SkillExecutor:
    """Get or create the global skill executor."""
    global _skill_executor
    if _skill_executor is None:
        _skill_executor = SkillExecutor(registry, config_dir, project_dir)
    return _skill_executor


__all__ = [
    # Manifest
    "SkillManifest",
    "SkillArgument",
    "SkillArgumentType",
    # Registry
    "SkillRegistry",
    "RegisteredSkill",
    "SkillScope",
    # Executor
    "SkillExecutor",
    "SkillResult",
    "SkillContext",
    "SkillExecutionMode",
    "SkillEvalFramework",
    "SkillSharing",
    "SkillCreator",
    # Eval
    "SkillEvaluator",
    "SkillTestSuite",
    "SkillTestCase",
    "SkillTestResult",
    "TestSeverity",
    # Helpers
    "get_skill_registry",
    "get_skill_executor",
]