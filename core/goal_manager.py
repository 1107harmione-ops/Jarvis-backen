"""
goal_manager.py — Manages user goals and their lifecycle.

A goal can span multiple tasks, sessions, and even survive restarts.
"""
import json, logging, os, time, uuid
from typing import Optional
from datetime import datetime

logger = logging.getLogger("goal_manager")

GOALS_FILE = "data/goals.json"


class Goal:
    """Represents a user goal with its execution state."""

    def __init__(self, description: str, goal_id: str = None,
                 status: str = "pending", created_at: float = None):
        self.id = goal_id or str(uuid.uuid4())[:8]
        self.description = description
        self.status = status  # pending | planning | executing | completed | failed | paused
        self.created_at = created_at or time.time()
        self.updated_at = self.created_at
        self.plan: list = []
        self.completed_tasks: list = []
        self.failed_tasks: list = []
        self.result: str = ""
        self.context: dict = {}

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "description": self.description,
            "status": self.status,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "plan": self.plan,
            "completed_tasks": self.completed_tasks,
            "failed_tasks": self.failed_tasks,
            "result": self.result,
            "context": self.context,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Goal":
        g = cls(data["description"], data["id"], data["status"], data["created_at"])
        g.updated_at = data.get("updated_at", g.updated_at)
        g.plan = data.get("plan", [])
        g.completed_tasks = data.get("completed_tasks", [])
        g.failed_tasks = data.get("failed_tasks", [])
        g.result = data.get("result", "")
        g.context = data.get("context", {})
        return g

    def __repr__(self):
        return f"<Goal {self.id}: {self.description[:40]} [{self.status}]>"


class GoalManager:
    """Manages persistence and lifecycle of goals."""

    def __init__(self, filepath: str = GOALS_FILE):
        self.filepath = filepath
        self.goals: dict[str, Goal] = {}
        self._ensure_dir()
        self._load()

    def _ensure_dir(self):
        os.makedirs(os.path.dirname(self.filepath) or ".", exist_ok=True)

    def _load(self):
        try:
            if os.path.exists(self.filepath):
                with open(self.filepath) as f:
                    data = json.load(f)
                    for gd in data:
                        g = Goal.from_dict(gd)
                        self.goals[g.id] = g
                logger.info("Loaded %d goals", len(self.goals))
        except Exception as e:
            logger.warning("Failed to load goals: %s", e)

    def _save(self):
        try:
            data = [g.to_dict() for g in self.goals.values()]
            with open(self.filepath, "w") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error("Failed to save goals: %s", e)

    def create_goal(self, description: str, context: dict = None) -> Goal:
        g = Goal(description)
        if context:
            g.context = context
        self.goals[g.id] = g
        self._save()
        logger.info("Created goal: %s", g)
        return g

    def get_goal(self, goal_id: str) -> Optional[Goal]:
        return self.goals.get(goal_id)

    def update_goal(self, goal_id: str, **kwargs) -> Optional[Goal]:
        g = self.goals.get(goal_id)
        if not g:
            return None
        for k, v in kwargs.items():
            if hasattr(g, k):
                setattr(g, k, v)
        g.updated_at = time.time()
        self._save()
        return g

    def list_goals(self, status: str = None, limit: int = 20) -> list:
        goals = list(self.goals.values())
        if status:
            goals = [g for g in goals if g.status == status]
        goals.sort(key=lambda g: g.updated_at, reverse=True)
        return [g.to_dict() for g in goals[:limit]]

    def delete_goal(self, goal_id: str) -> bool:
        if goal_id in self.goals:
            del self.goals[goal_id]
            self._save()
            return True
        return False

    def cleanup_old(self, max_age_hours: int = 72):
        """Remove completed/failed goals older than max_age_hours."""
        cutoff = time.time() - (max_age_hours * 3600)
        to_remove = [gid for gid, g in self.goals.items()
                     if g.status in ("completed", "failed") and g.created_at < cutoff]
        for gid in to_remove:
            del self.goals[gid]
        if to_remove:
            self._save()
            logger.info("Cleaned up %d old goals", len(to_remove))
