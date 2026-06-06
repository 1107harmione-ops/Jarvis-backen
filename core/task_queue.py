"""
task_queue.py — Async task queue for executing plans.

Handles sequential and parallel task execution with dependency resolution.
"""
import logging, time
from typing import Optional
from core.tool_executor import ToolExecutor

logger = logging.getLogger("task_queue")


class TaskQueue:
    """Executes a list of tasks respecting dependencies."""

    def __init__(self):
        self.executor = ToolExecutor()

    def execute(self, tasks: list, knowledge_context: str = "") -> list:
        """Execute tasks in dependency order."""
        results = []
        completed = {}

        sorted_tasks = self._topological_sort(tasks)

        for task in sorted_tasks:
            dep_id = task.get("depends_on")
            if dep_id is not None:
                if dep_id not in completed:
                    logger.warning("Dependency task %s not completed, skipping %s",
                                   dep_id, task.get("id"))
                    results.append({
                        "success": False,
                        "error": f"Dependency task {dep_id} not completed",
                        "_task_id": task.get("id"),
                    })
                    continue
                # Pass dependency result as context
                task.setdefault("parameters", {})
                task["parameters"]["_dependency_result"] = \
                    completed[dep_id].get("result", "")

            try:
                result = self.executor.execute_task(task, knowledge_context)
                result["_task_id"] = task.get("id")
                result["_task_goal"] = task.get("goal", "")
                completed[task.get("id")] = result
                results.append(result)
                logger.info("Task %s completed: %s", task.get("id"),
                            result.get("success"))
            except Exception as e:
                err_result = {
                    "success": False,
                    "error": str(e),
                    "_task_id": task.get("id"),
                    "_task_goal": task.get("goal", ""),
                }
                completed[task.get("id")] = err_result
                results.append(err_result)
                logger.error("Task %s failed: %s", task.get("id"), e)

        return results

    def execute_with_retry(self, tasks: list, knowledge_context: str = "",
                           max_retries: int = 2) -> list:
        """Execute with retry for failed tasks."""
        results = self.execute(tasks, knowledge_context)

        for i, (task, result) in enumerate(zip(tasks, results)):
            if not result.get("success") and max_retries > 0:
                logger.info("Retrying task %s (attempts left: %s)",
                            task.get("id"), max_retries)
                retry = self.executor.execute_task(task, knowledge_context)
                retry["_task_id"] = task.get("id")
                retry["_retry"] = True
                results[i] = retry

        return results

    def _topological_sort(self, tasks: list) -> list:
        """Sort tasks so dependencies come before dependents."""
        sorted_tasks = []
        visited = set()
        task_map = {t.get("id"): t for t in tasks}

        def visit(task_id):
            if task_id in visited:
                return
            visited.add(task_id)
            task = task_map.get(task_id)
            if task:
                dep_id = task.get("depends_on")
                if dep_id is not None and dep_id in task_map:
                    visit(dep_id)
                sorted_tasks.append(task)

        for task in tasks:
            visit(task.get("id"))

        return sorted_tasks
