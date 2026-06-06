"""Episodic Memory - High-level event/experience logging."""

import time
import json
from .database_memory import DatabaseMemory


class EpisodicMemory:
    """High-level episodic memory — logs major events and extracts insights."""

    def __init__(self, db_memory: DatabaseMemory = None):
        self.db = db_memory or DatabaseMemory()

    def record_event(self, session_id: str, event_type: str, summary: str, details: dict = None):
        """Record a notable event in the session."""
        self.db.store_episode(session_id, event_type, summary, details)

    def record_command(self, session_id: str, command: str, result: str = None, success: bool = True):
        """Record a user command and its outcome."""
        self.db.store_episode(
            session_id, "command",
            f"Command: {command[:100]}{'...' if len(command) > 100 else ''}",
            {"command": command, "result": result, "success": success}
        )

    def record_goal(self, session_id: str, goal: str, status: str, result: str = None):
        """Record a goal lifecycle event."""
        self.db.store_episode(
            session_id, "goal",
            f"Goal {status}: {goal[:100]}",
            {"goal": goal, "status": status, "result": result}
        )

    def record_error(self, session_id: str, error: str, context: dict = None):
        """Record an error/failure event."""
        self.db.store_episode(
            session_id, "error",
            f"Error: {error[:200]}",
            {"error": error, "context": context or {}}
        )

    def get_session_story(self, session_id: str, limit: int = 50) -> list:
        """Get the narrative story of a session — ordered events."""
        return self.db.get_recent_episodes(session_id, limit)

    def get_recent_events(self, limit: int = 100) -> list:
        """Get recent events across all sessions."""
        return self.db.get_all_episodes(limit)

    def get_summary(self, session_id: str, max_events: int = 10) -> str:
        """Generate a human-readable summary of the session's key events."""
        events = self.get_session_story(session_id, max_events)
        if not events:
            return "No significant events recorded."

        lines = ["📋 Session Summary:", "─" * 40]
        for ev in reversed(events):
            ts = time.strftime("%H:%M:%S", time.localtime(ev["timestamp"]))
            icon = {"command": "⚡", "goal": "🎯", "error": "❌", "system": "🔧"}.get(ev["type"], "📌")
            lines.append(f"{icon} [{ts}] {ev['type'].upper()}: {ev['summary']}")

        return "\n".join(lines)
