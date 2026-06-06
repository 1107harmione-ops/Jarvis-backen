"""
replanner.py — Dynamic replanning for failed or evolving goals.

Monitors goal progress and generates new plans when tasks fail
or user provides additional context.
"""
import logging
from typing import Optional
from core.planner_agent import plan
from core.goal_manager import GoalManager

logger = logging.getLogger("replanner")


class Replanner:
    """Handles dynamic replanning when tasks fail or goals change."""

    def __init__(self):
        self.goal_manager = GoalManager()

    def replan_failed_goal(self, goal_id: str, failure_reason: str = "") -> Optional[list]:
        """Replan a failed goal, learning from the failure."""
        goal = self.goal_manager.get_goal(goal_id)
        if not goal:
            return None

        context = {
            "original_goal": goal.description,
            "failure_reason": failure_reason,
            "completed_tasks": goal.completed_tasks,
            "failed_tasks": goal.failed_tasks,
            "previous_plan": goal.plan,
        }

        revised_prompt = goal.description
        if failure_reason:
            revised_prompt += f"\n\nNote: Previous attempt failed because: {failure_reason}"

        logger.info("Replanning goal %s: %s", goal_id, revised_prompt[:60])
        new_tasks = plan(revised_prompt, context)

        if new_tasks and len(new_tasks) > 0:
            self.goal_manager.update_goal(goal_id, plan=new_tasks, status="executing")
            return new_tasks

        return None

    def optimize_plan(self, goal_id: str, execution_history: list) -> Optional[list]:
        """Optimize remaining tasks based on execution history."""
        goal = self.goal_manager.get_goal(goal_id)
        if not goal or not goal.plan:
            return None

        remaining = [t for t in goal.plan
                     if t.get("id") not in goal.completed_tasks]

        if not remaining:
            return []

        # For now, just return remaining tasks
        # Future: use LLM to reorder/optimize
        return remaining
