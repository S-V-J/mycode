"""Artifacts system for MyCode - visual outputs in TUI."""

from .renderer import (
    ArtifactRenderer,
    ArtifactManager,
    Artifact,
    ArtifactType,
    InteractiveArtifact,
    FormArtifact,
    SliderArtifact,
    ToggleArtifact,
    MCPArtifactConnector,
)

from .connector import (
    MCPArtifactConnector,
    ConnectorStatus,
    MCPResourceSubscription,
    MCPToolBinding,
    ArtifactDataSource,
    MCPResourceDataSource,
    MCPToolDataSource,
    StaticDataSource,
    CompositeDataSource,
    LiveArtifactUpdater,
)

# Global instance
_artifact_manager = None


def get_artifact_manager(config_dir: Path) -> ArtifactManager:
    """Get or create the global artifact manager."""
    global _artifact_manager
    if _artifact_manager is None:
        _artifact_manager = ArtifactManager(config_dir)
    return _artifact_manager


__all__ = [
    # Renderer
    "ArtifactRenderer",
    "ArtifactManager",
    "Artifact",
    "ArtifactType",
    "InteractiveArtifact",
    "FormArtifact",
    "SliderArtifact",
    "ToggleArtifact",
    # Connector
    "MCPArtifactConnector",
    "ConnectorStatus",
    "MCPResourceSubscription",
    "MCPToolBinding",
    "ArtifactDataSource",
    "MCPResourceDataSource",
    "MCPToolDataSource",
    "StaticDataSource",
    "CompositeDataSource",
    "LiveArtifactUpdater",
    # Helpers
    "get_artifact_manager",
]