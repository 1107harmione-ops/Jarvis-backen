"""
tool_executor.py — Executes tool actions from planner tasks.

Takes a task from the planner and runs it through the tool registry
or falls back to agent execution.
"""
import json, logging
from typing import Optional
from core.tool_registry import get_registry
from agents.base_agent import BaseAgent

logger = logging.getLogger("tool_executor")


class ToolExecutor:
    """Executes tool actions and agent tasks with verification support."""

    def __init__(self):
        self._agent_cache = {}
        self._agent_classes = {
            "search": "agents.search_agent.SearchAgent",
            "research": "agents.research_agent.ResearchAgent",
            "coding": "agents.coding_agent.CodingAgent",
            "image": "agents.image_agent.ImageAgent",
            "task": "agents.task_agent.TaskAgent",
            "reasoning": "agents.reasoning_agent.ReasoningAgent",
            "chat": None,  # handled by orchestrator directly
        }

    def execute_task(self, task: dict, knowledge_context: str = "") -> dict:
        """Execute a single planner task."""
        agent_name = task.get("agent", "chat")
        goal = task.get("goal", "")
        params = task.get("parameters", {})

        # Try tool registry first
        registry = get_registry()
        tool_name = params.get("action") or agent_name
        if registry.has_tool(tool_name):
            logger.info("Executing tool: %s | goal: %s", tool_name, goal[:60])
            result = registry.execute(tool_name, **params)
            return self._format_result(result, agent_name, tool_name)

        # Try agent
        agent = self._get_agent(agent_name)
        if agent:
            if knowledge_context:
                agent.knowledge_context = knowledge_context
            logger.info("Executing agent: %s | goal: %s", agent_name, goal[:60])
            return agent.run(goal, params)

        # Fallback: return goal as result
        logger.warning("No handler for agent=%s, returning goal as result", agent_name)
        return {"agent": agent_name, "success": True, "result": goal,
                "metadata": {"note": "no handler available"}}

    def execute_plan(self, tasks: list, knowledge_context: str = "") -> list:
        """Execute a full plan respecting dependencies."""
        results = []
        completed = {}

        for task in tasks:
            dep_id = task.get("depends_on")
            if dep_id is not None and dep_id in completed:
                # Pass dependency result as context
                dep_result = completed[dep_id]
                task.setdefault("parameters", {})
                task["parameters"]["_dependency_result"] = dep_result

            result = self.execute_task(task, knowledge_context)
            task_id = task.get("id", 0)
            result["_task_id"] = task_id
            result["_task_goal"] = task.get("goal", "")
            completed[task_id] = result
            results.append(result)

        return results

    def _get_agent(self, name: str) -> Optional[BaseAgent]:
        if name in self._agent_cache:
            return self._agent_cache[name]
        path = self._agent_classes.get(name)
        if not path:
            return None
        try:
            module_name, class_name = path.rsplit(".", 1)
            import importlib
            mod = importlib.import_module(module_name)
            cls = getattr(mod, class_name)
            agent = cls()
            self._agent_cache[name] = agent
            return agent
        except Exception as e:
            logger.error("Failed to load agent '%s': %s", name, e)
            return None

    def _format_result(self, result: dict, agent: str, tool: str) -> dict:
        return {
            "agent": agent,
            "tool": tool,
            "success": result.get("success", False),
            "result": result.get("result", result.get("error", "")),
            "metadata": result.get("metadata", {}),
        }
