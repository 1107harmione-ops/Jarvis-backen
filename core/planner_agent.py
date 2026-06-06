"""
planner_agent.py — Intelligent task planner for JARVIS.

Replaces keyword routing with LLM-powered goal decomposition.
Breaks user goals into executable subtasks, assigns agents,
and supports dependency resolution.
"""
import json, logging, re
from typing import Optional
from core.provider_manager import llm_completion

logger = logging.getLogger("planner")

PLANNER_SYSTEM_PROMPT = """You are JARVIS Planner, an intelligent task decomposition engine.

Your job is to understand the user's goal and break it into a sequence of executable subtasks.

AGENTS AVAILABLE:
- search: Quick web search, news, weather, prices, facts
- research: Deep multi-source research, comprehensive analysis
- coding: Write, debug, explain, refactor code
- image: Generate or create images
- task: Execute device actions (open/close apps, toggle settings)
- reasoning: Math, planning, analysis, decision making
- vision: Analyze images, OCR, screenshot understanding
- chat: General conversation, answering questions
- verifier: Check if a task was completed successfully
- memory: Store or retrieve information

Return ONLY valid JSON. No markdown, no explanation.

Example 1 — Simple:
Input: "what's the weather in Tokyo"
Output: {"tasks":[{"id":1,"agent":"search","goal":"Find current weather in Tokyo","parameters":{"query":"Tokyo weather 2026"}}]}

Example 2 — Multi-step:
Input: "research AI news and save it"
Output: {"tasks":[{"id":1,"agent":"search","goal":"Find latest AI news articles","parameters":{"query":"artificial intelligence news 2026"}},{"id":2,"agent":"research","goal":"Summarize the AI news findings","parameters":{"query":"AI news summary"},"depends_on":1},{"id":3,"agent":"memory","goal":"Store the research summary","parameters":{},"depends_on":2}]}

Example 3 — Device action:
Input: "open WhatsApp and send a message to mom"
Output: {"tasks":[{"id":1,"agent":"task","goal":"Open WhatsApp application","parameters":{"action":"open_app","target":"whatsapp"}},{"id":2,"agent":"task","goal":"Send message to mom","parameters":{"action":"send_whatsapp","target":"mom","message":""},"depends_on":1}]}

Rules:
- Break complex goals into the smallest reasonable steps
- Use depends_on for sequential dependencies (1-indexed task IDs)
- Parameters should contain all needed context from the user's query
- For chat/general questions, use a single task with agent="chat"
- Maximum 5 tasks per plan
"""


def plan(goal: str, context: Optional[dict] = None) -> list:
    """Generate a task plan for a user goal.

    Returns a list of task dicts:
        [{"id": int, "agent": str, "goal": str, "parameters": dict, "depends_on": int}]
    """
    messages = [{"role": "user", "content": goal}]
    if context:
        context_str = json.dumps(context, indent=2)
        messages.insert(0, {"role": "system",
                            "content": f"User context:\n{context_str}\n\n{PLANNER_SYSTEM_PROMPT}"})

    raw = llm_completion(
        messages=messages,
        system=PLANNER_SYSTEM_PROMPT if not context else None,
        temperature=0.1,
        max_tokens=1500,
    )
    try:
        m = re.search(r"\{.*\}", raw, re.DOTALL)
        if m:
            data = json.loads(m.group())
            tasks = data.get("tasks", [])
            # Validate
            validated = []
            for t in tasks:
                if all(k in t for k in ("id", "agent", "goal")):
                    t.setdefault("parameters", {})
                    t.setdefault("depends_on", None)
                    validated.append(t)
            if validated:
                logger.info("Planner: %s -> %d tasks", goal[:50], len(validated))
                return validated
    except (json.JSONDecodeError, AttributeError) as e:
        logger.warning("Planner parse error: %s | raw: %s", e, raw[:200])

    # Fallback: single chat task
    logger.info("Planner fallback: treating as chat task")
    return [{"id": 1, "agent": "chat", "goal": goal, "parameters": {}, "depends_on": None}]


def plan_with_retry(goal: str, context: Optional[dict] = None, max_retries: int = 2) -> list:
    """Plan with retry on failure."""
    for attempt in range(max_retries):
        tasks = plan(goal, context)
        if len(tasks) > 0 and tasks[0]["agent"] != "chat":
            return tasks
        if attempt == 0 and len(tasks) == 1 and tasks[0]["agent"] == "chat":
            # Single chat task is valid — return it
            return tasks
    return plan(goal, context)
