"""
workflow_engine.py — Manages autonomous workflow execution.

Handles long-running goals with dynamic replanning and recovery.
"""
import json, logging, time
from typing import Optional
from core.goal_manager import GoalManager
from core.planner_agent import plan
from core.task_queue import TaskQueue
from agents.verifier_agent import VerifierAgent

logger = logging.getLogger("workflow_engine")


class WorkflowEngine:
    """Orchestrates the full goal lifecycle: Plan → Execute → Verify → Recover → Complete."""

    def __init__(self, max_retries: int = 2):
        self.goal_manager = GoalManager()
        self.task_queue = TaskQueue()
        self.verifier = VerifierAgent(max_retries=max_retries)
        self._knowledge_context = ""

    def process_goal(self, description: str, context: dict = None) -> dict:
        """Process a user goal end-to-end."""
        # 1. Create goal
        goal = self.goal_manager.create_goal(description, context)
        logger.info("Processing goal: %s", goal)

        # 2. Plan
        self.goal_manager.update_goal(goal.id, status="planning")
        tasks = plan(description, context)
        if not tasks:
            goal.result = "I couldn't figure out how to do that. Please be more specific."
            self.goal_manager.update_goal(goal.id, status="failed", result=goal.result)
            return {"goal_id": goal.id, "status": "failed", "result": goal.result}

        self.goal_manager.update_goal(goal.id, plan=tasks, status="executing")

        # 3. Execute
        results = self.task_queue.execute_with_retry(
            tasks, self._knowledge_context, max_retries=1
        )

        # 4. Verify
        verifications = self.verifier.verify_plan(tasks, results)
        failed_indices = [i for i, v in enumerate(verifications)
                          if self.verifier.needs_retry(v)]

        # 5. Retry failed tasks
        retry_count = 0
        while failed_indices and retry_count < self.max_retries:
            retry_count += 1
            logger.info("Retrying %d failed tasks (attempt %d/%d)",
                        len(failed_indices), retry_count, self.max_retries)
            for idx in failed_indices:
                retry_result = self.task_queue.executor.execute_task(
                    tasks[idx], self._knowledge_context
                )
                results[idx] = retry_result
            verifications = self.verifier.verify_plan(tasks, results)
            failed_indices = [i for i, v in enumerate(verifications)
                              if self.verifier.needs_retry(v)]

        # 6. Compile result
        success_count = sum(1 for r in results if r.get("success"))
        total = len(results)
        all_success = success_count == total
        status = "completed" if all_success else "completed_with_errors"

        # Build response text
        response_parts = []
        for task, result in zip(tasks, results):
            if result.get("success"):
                r = result.get("result", "")
                if r:
                    response_parts.append(r)
            else:
                response_parts.append(
                    f"⚠️ {task.get('goal', '')[:60]} — failed"
                )

        goal.result = "\n".join(response_parts) if response_parts else "Done."
        completed_ids = [t.get("id") for t, r in zip(tasks, results) if r.get("success")]
        failed_ids = [t.get("id") for t, r in zip(tasks, results) if not r.get("success")]

        self.goal_manager.update_goal(
            goal.id, status=status, result=goal.result,
            completed_tasks=completed_ids, failed_tasks=failed_ids,
        )

        return {
            "goal_id": goal.id,
            "status": status,
            "result": goal.result,
            "tasks_total": total,
            "tasks_completed": success_count,
            "tasks_failed": total - success_count,
        }

    def replan(self, goal_id: str, feedback: str = "") -> Optional[dict]:
        """Replan a failed or paused goal with user feedback."""
        goal = self.goal_manager.get_goal(goal_id)
        if not goal:
            return None

        revised_description = goal.description
        if feedback:
            revised_description = f"{goal.description}\nUser feedback: {feedback}"

        # Reset and re-process
        self.goal_manager.update_goal(goal.id, status="planning",
                                       plan=[], completed_tasks=[], failed_tasks=[])
        return self.process_goal(revised_description, goal.context)
