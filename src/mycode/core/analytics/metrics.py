"""Analytics collection for MyCode."""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Dict, Any, List
import threading


@dataclass
class TokenUsage:
    """Token usage for a single request."""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0


@dataclass
class SessionMetrics:
    """Metrics for a single session."""
    session_id: str
    started_at: str = field(default_factory=lambda: datetime.now().isoformat())
    ended_at: Optional[str] = None
    messages_sent: int = 0
    messages_received: int = 0
    tools_executed: int = 0
    cache_hits: int = 0
    cache_misses: int = 0
    total_tokens: int = 0
    errors: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "session_id": self.session_id,
            "started_at": self.started_at,
            "ended_at": self.ended_at,
            "messages_sent": self.messages_sent,
            "messages_received": self.messages_received,
            "tools_executed": self.tools_executed,
            "cache_hits": self.cache_hits,
            "cache_misses": self.cache_misses,
            "total_tokens": self.total_tokens,
            "errors": self.errors,
        }


class AnalyticsCollector:
    """Collect analytics events."""

    def __init__(self):
        self.sessions: Dict[str, SessionMetrics] = {}
        self._lock = threading.Lock()
        self._current_session: Optional[str] = None

    def start_session(self, session_id: str):
        with self._lock:
            self._current_session = session_id
            self.sessions[session_id] = SessionMetrics(session_id=session_id)

    def end_session(self, session_id: str):
        with self._lock:
            if session_id in self.sessions:
                self.sessions[session_id].ended_at = datetime.now().isoformat()

    def record_message(self, session_id: str, role: str):
        with self._lock:
            if session_id in self.sessions:
                if role == "user":
                    self.sessions[session_id].messages_sent += 1
                else:
                    self.sessions[session_id].messages_received += 1

    def record_tool_execution(self, session_id: str, tool_name: str):
        with self._lock:
            if session_id in self.sessions:
                self.sessions[session_id].tools_executed += 1

    def record_cache_hit(self, session_id: str):
        with self._lock:
            if session_id in self.sessions:
                self.sessions[session_id].cache_hits += 1

    def record_cache_miss(self, session_id: str):
        with self._lock:
            if session_id in self.sessions:
                self.sessions[session_id].cache_misses += 1

    def record_tokens(self, session_id: str, usage: TokenUsage):
        with self._lock:
            if session_id in self.sessions:
                self.sessions[session_id].total_tokens += usage.total_tokens

    def record_error(self, session_id: str):
        with self._lock:
            if session_id in self.sessions:
                self.sessions[session_id].errors += 1

    def get_session(self, session_id: str) -> Optional[SessionMetrics]:
        with self._lock:
            return self.sessions.get(session_id)

    def get_all_sessions(self) -> List[SessionMetrics]:
        with self._lock:
            return list(self.sessions.values())


# Global instance
_analytics = AnalyticsCollector()


def get_analytics() -> AnalyticsCollector:
    return _analytics
