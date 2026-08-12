"""Metrics export for MyCode analytics."""
import json
from pathlib import Path
from typing import Optional
from datetime import datetime


class MetricsExporter:
    """Export metrics to various formats."""

    def __init__(self, output_dir: Optional[Path] = None):
        self.output_dir = output_dir or (Path.home() / ".mycode" / "analytics")
        self.output_dir.mkdir(exist_ok=True)

    def export_json(self, data: dict, filename: Optional[str] = None) -> str:
        """Export metrics as JSON."""
        if not filename:
            filename = f"metrics_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        filepath = self.output_dir / filename
        filepath.write_text(json.dumps(data, indent=2, default=str))
        return str(filepath)

    def export_session_summary(self, session_metrics, cost_summary: dict) -> str:
        """Export a session summary."""
        data = {
            "timestamp": datetime.now().isoformat(),
            "session": session_metrics.to_dict() if hasattr(session_metrics, "to_dict") else session_metrics,
            "costs": cost_summary,
        }
        return self.export_json(data, f"session_{data['session'].get('session_id', 'unknown')}.json")

    def export_cost_report(self, cost_tracker) -> str:
        """Export cost report."""
        summary = cost_tracker.get_summary()
        return self.export_json(summary, "cost_report.json")
