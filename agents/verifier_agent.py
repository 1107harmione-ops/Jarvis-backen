"""
verifier_agent.py — Verifies that tasks were completed successfully.

Checks execution results, retries on failure, and triggers recovery.
"""
import json, logging, time
from typing import Optional
from core.provider_manager import llm_completion

logger = logging.getLogger("verifier")

VERIFIER_SYSTEM_PROMPT = """You are JARVIS Verifier. Your job is to check if a task was completed successfully.

Given a task description and the execution result, determine:
1. Was the task actually completed?
2. Is the result meaningful/accurate?
3. Should it be retried?

Output JSON:
{"success": true/false, "reason": "why", "should_retry": true/false, "retry_count": 0}

Rules:
- If the result contains useful information, it's a success
- If the result is an error or empty, it's a failure
- If should_retry is true, the orchestrator will retry
- Set retry_count to how many times it should retry (max 3)
"""


class VerifierAgent:
    """Verifies task execution and handles retries."""

    def __init__(self, max_retries: int = 3):
        self.max_retries = max_retries

    def verify(self, task: dict, result: dict) -> dict:
        """Verify a single task execution result."""
        if result.get("success", False):
            return {
                "verified": True,
                "reason": "Execution reported success",
                "should_retry": False,
                "retry_count": 0,
            }

        # Use LLM to verify ambiguous cases
        task_goal = task.get("goal", "")
        task_agent = task.get("agent", "")
        result_text = str(result.get("result", ""))
        error = result.get("error", "")

        prompt = f"""Task: {task_goal}
Agent: {task_agent}
Result: {result_text[:500]}
Error: {error[:200]}"""

        try:
            raw = llm_completion(
                messages=[{"role": "user", "content": prompt}],
                system=VERIFIER_SYSTEM_PROMPT,
                temperature=0.0,
                max_tokens=300,
            )
            import re
            m = re.search(r"\{.*\}", raw, re.DOTALL)
            if m:
                data = json.loads(m.group())
                return {
                    "verified": data.get("success", False),
                    "reason": data.get("reason", ""),
                    "should_retry": data.get("should_retry", False),
                    "retry_count": min(data.get("retry_count", 1), self.max_retries),
                }
        except Exception as e:
            logger.warning("Verifier LLM error: %s", e)

        # Fallback: check if result has content
        has_content = bool(result_text.strip()) if result_text else False
        return {
            "verified": has_content and result.get("success", False),
            "reason": "Fallback verification: result has content" if has_content else "Empty result",
            "should_retry": not has_content,
            "retry_count": 1 if not has_content else 0,
        }

    def verify_plan(self, tasks: list, results: list) -> list:
        """Verify all tasks in a plan."""
        verifications = []
        for task, result in zip(tasks, results):
            v = self.verify(task, result)
            v["_task_id"] = task.get("id", 0)
            v["_task_goal"] = task.get("goal", "")
            verifications.append(v)
        return verifications

    def needs_retry(self, verification: dict) -> bool:
        return verification.get("should_retry", False) and verification.get("retry_count", 0) > 0
