"""JARVIS Orchestrator — Routes queries to agents, tools, or autonomous workflows.

V3 Integration:
  - provider_manager.llm_completion() for all LLM calls
  - planner_agent for goal decomposition
  - WorkflowEngine for autonomous task execution
  - VerifierAgent for result verification
  - ToolExecutor for tool-based actions
"""

import json, os, re, time, requests, logging
from core.config import GROQ_API_BASE, GROQ_CHAT_API_KEY, GROQ_CHAT_MODEL
from core.data_center import DataCenter
from core.auto_skill import SkillLibrary
from core.memory import Memory

# ── V3 Imports ──
from core.provider_manager import llm_completion, get_provider_manager

# Lazy imports for V3 modules (they may import each other)
_planner = None
_workflow_engine = None
_verifier = None
_tool_executor = None
_db_memory = None

logger = logging.getLogger("orchestrator")

_session = requests.Session()
_mem = Memory()
_datacenter = DataCenter()
_skill_lib = SkillLibrary()
TRAINING_DIR = "training_data"


def _get_planner():
    global _planner
    if _planner is None:
        from core.planner_agent import plan
        _planner = plan
    return _planner

def _get_workflow_engine():
    global _workflow_engine
    if _workflow_engine is None:
        from core.workflow_engine import WorkflowEngine
        _workflow_engine = WorkflowEngine()
    return _workflow_engine

def _get_verifier():
    global _verifier
    if _verifier is None:
        from agents.verifier_agent import VerifierAgent
        _verifier = VerifierAgent()
    return _verifier

def _get_tool_executor():
    global _tool_executor
    if _tool_executor is None:
        from core.tool_executor import ToolExecutor
        _tool_executor = ToolExecutor()
    return _tool_executor

def _get_db_memory():
    global _db_memory
    if _db_memory is None:
        from memory.database_memory import DatabaseMemory
        _db_memory = DatabaseMemory()
    return _db_memory


def load_training_data():
    all_knowledge = []
    all_sources = []
    if os.path.exists(TRAINING_DIR):
        for f in os.listdir(TRAINING_DIR):
            if f.endswith("_memory.json"):
                try:
                    filepath = os.path.join(TRAINING_DIR, f)
                    with open(filepath, "r", encoding="utf-8") as file:
                        data = json.load(file)
                        for entry in data.get("knowledge_base", []):
                            topic = entry.get("topic", "")
                            insight = entry.get("insight", "")
                            if topic and insight:
                                all_knowledge.append(f"Topic: {topic}\nInsight: {insight}")
                                if "Sources:" in insight:
                                    sources_section = insight.split("Sources:")[-1].strip()
                                    for line in sources_section.split("\n"):
                                        if line.strip():
                                            all_sources.append(line.strip())
                except Exception as e:
                    print(f"Warning: Failed to load training file {f}: {e}")
    return all_knowledge, all_sources


def get_training_context(max_entries=50):
    knowledge, sources = load_training_data()
    recent_knowledge = knowledge[-max_entries:] if len(knowledge) > max_entries else knowledge
    knowledge_str = "\n\n".join(recent_knowledge)
    sources_str = "\n".join(sources[-20:]) if sources else "No sources collected yet."
    return f"""--- TRAINED KNOWLEDGE BASE ---
{knowledge_str}

--- COLLECTED SOURCES ---
{sources_str}
--- END KNOWLEDGE BASE ---"""


_AGENT_CLASSES = {
    "coding": "agents.coding_agent.CodingAgent",
    "image": "agents.image_agent.ImageAgent",
    "task": "agents.task_agent.TaskAgent",
    "research": "agents.research_agent.ResearchAgent",
    "search": "agents.search_agent.SearchAgent",
    "reasoning": "agents.reasoning_agent.ReasoningAgent",
}

_agent_cache = {}


def _get_agent(name: str):
    if name not in _agent_cache:
        path = _AGENT_CLASSES.get(name, "")
        if not path:
            return None
        module_name, class_name = path.rsplit(".", 1)
        import importlib
        mod = importlib.import_module(module_name)
        cls = getattr(mod, class_name)
        _agent_cache[name] = cls()
    return _agent_cache[name]


CLASSIFY_SYSTEM = """You are JARVIS, an intelligent command router. 
Classify the user's query and route it to the correct agent(s).

AGENTS:
- coding: write/run/debug/explain/improve code in any language
- image: generate, create, draw pictures/images/artwork
- task: open/close apps, volume, brightness, wifi, bluetooth, screenshot, call, notes, battery, time, shutdown
- research: deep research on a topic, multi-source information, comprehensive answers
- search: quick facts, news, weather, prices, sports scores, real-time data
- reasoning: math, calculations, planning, pros/cons, decision making, analysis
- goal: multi-step autonomous goals, complex workflows, "I want you to..." or "can you handle..."
- chat: general conversation, questions, advice, anything else

Return ONLY valid JSON:
{
  "primary_agent": "coding|image|task|research|search|reasoning|goal|chat",
  "secondary_agents": [],
  "confidence": "high|medium|low",
  "query_for_agent": "<query refined for the agent>",
  "parameters": {}
}

Rules:
- Use "search" for quick lookups, "research" for detailed multi-source analysis
- Use "task" for any device/app/system control
- Use "reasoning" for math, planning, multi-step problems
- Use "goal" for multi-step, autonomous tasks like "research X and then summarize"
- secondary_agents: list at most 1 secondary agent that should run AFTER primary
- query_for_agent: clean up the user input for the selected agent
"""

_KEYWORD_ROUTES = [
    (["write code", "code for", "program to", "script to", "write a function", "write python", "write javascript", "write java", "debug this", "fix this code", "explain this code", "refactor", "how to code", "implement", "build a", "build an", "write a code", "write program", "create a function", "make a program", "generate code"], "coding"),
    (["generate image", "create image", "draw", "make a picture", "make an image", "generate a photo", "create art", "generate art", "paint"], "image"),
    (["open ", "close ", "launch ", "play ", "youtube", "volume", "brightness", "wifi", "bluetooth", "screenshot", "lock", "shutdown", "restart", "battery", "call ", "take photo", "gallery", "files", "storage", "notification", "remind ", "increase", "decrease", "dim", "turn up", "turn down", "turn on", "turn off", "search ", "google", "browser", "camera", "spotify", "telegram", "whatsapp", "sms", "inbox", "contacts", "song", "music", "media", "next ", "previous ", "pause ", "wallpaper", "location", "share ", "call log", "what time", "current time", "check time"], "task"),
    (["research", "in-depth", "comprehensive", "tell me everything about", "deep dive", "history of", "explain in detail", "what is everything about", "detailed explanation"], "research"),
    (["news", "latest", "current", "today", "temperature", "weather", "price of", "stock", "score", "who is", "what is", "when did", "how tall", "how old", "define ", "meaning of", "translate"], "search"),
    (["calculate", "solve", "equation", "math", "compute", "how much is", "percentage of", "what is the total", "plan for", "roadmap", "should i", "pros and cons", "compare these", "analyze", "why does"], "reasoning"),
    (["i want you to", "can you handle", "autonomous", "multi-step", "goal", "workflow", "go ahead and", "take care of", "handle everything", "orchestrate", "manage this"], "goal"),
]


def _keyword_classify(query: str) -> str:
    q = query.lower()
    for keywords, agent in _KEYWORD_ROUTES:
        if any(kw in q for kw in keywords):
            return agent
    return "chat"


def _llm_classify(query: str) -> dict:
    try:
        result = llm_completion(
            [{"role": "user", "content": query}],
            system=CLASSIFY_SYSTEM,
            temperature=0.0,
            max_tokens=300
        )
        if result and not result.startswith("[All LLM providers"):
            m = re.search(r"\{.*\}", result, re.DOTALL)
            if m:
                return json.loads(m.group())
    except Exception:
        pass
    return {}


def _chat_response(query: str, knowledge_context: str = "", session_id: str = "") -> str:
    enriched_query = query
    if knowledge_context:
        enriched_query = f"[Knowledge Context]\n{knowledge_context}\n\n[User Query]\n{query}"
    response = llm_completion(
        [{"role": "user", "content": enriched_query}],
        system="You are JARVIS, an advanced AI assistant. Be helpful, concise, and accurate."
    )
    if response.startswith("[All LLM providers"):
        response = "I'm having trouble connecting to my neural core. Please check my API connections."
    if session_id:
        try:
            _mem.add_with_session("user", query, session_id)
            _mem.add_with_session("assistant", response, session_id)
            _get_db_memory().store_message(session_id, "user", query)
            _get_db_memory().store_message(session_id, "assistant", response)
        except Exception:
            pass
    else:
        _mem.add("user", query)
        _mem.add("assistant", response)
    return response


class Orchestrator:
    def __init__(self, use_llm_classify: bool = True):
        self.use_llm_classify = use_llm_classify
        self._last_query = ""

    def run(self, query: str, context: dict = None, session_id: str = "") -> dict:
        if not query or not query.strip():
            return self._make_response("I didn't catch that. Please repeat.", agent="orchestrator", success=False)
        start = time.time()
        query = query.strip()
        knowledge_context = _datacenter.get_context(query=query, limit=3)
        auto_skills = _skill_lib.get_relevant(query, limit=2)
        classification = self._classify(query)
        primary = classification.get("primary_agent", "chat")
        secondary = classification.get("secondary_agents", [])
        refined_query = classification.get("query_for_agent", query)
        parameters = classification.get("parameters", {})
        if auto_skills:
            skills_text = "\n\n".join(
                f"[Skill: {s['name']}]\n{s['description']}\nSteps: " + "; ".join(s.get("steps", []))
                for s in auto_skills
            )
            parameters.setdefault("knowledge_context", "")
            parameters["knowledge_context"] += f"\n\n--- RELEVANT AUTO-SKILLS ---\n{skills_text}\n--- END SKILLS ---"
        if knowledge_context:
            parameters["knowledge_context"] = knowledge_context

        print(f"[Orchestrator] '{query[:60]}' -> agent={primary}")

        # ── V3: Goal / autonomous workflow ──
        if primary == "goal":
            try:
                workflow = _get_workflow_engine()
                result = workflow.process_goal(refined_query, {"session_id": session_id})
                response_text = result.get("summary", "") or result.get("status", "Goal processing complete.")
                success = result.get("status") != "failed"
                metadata = {"goal_id": result.get("goal_id"), "tasks_completed": result.get("tasks_completed", 0)}
                print(f"[Orchestrator] Goal complete: {result.get('status')} | {metadata.get('tasks_completed', 0)} tasks")
            except Exception as e:
                logger.error("WorkflowEngine error: %s", e)
                response_text = f"I encountered an error while processing your goal: {e}"
                success = False
                metadata = {}

        elif primary == "chat":
            response_text = _chat_response(query, knowledge_context, session_id)
            metadata = {}
            success = True
        else:
            agent = _get_agent(primary)
            if not agent:
                response_text = _chat_response(query, knowledge_context, session_id)
                metadata = {}
                success = True
                primary = "chat"
            else:
                agent.knowledge_context = knowledge_context
                result = agent.run(refined_query, parameters)
                response_text = str(result.get("result", ""))
                metadata = result.get("metadata", {})
                success = result.get("success", True)

        # ── Secondary agents ──
        if secondary and success:
            for sec_name in secondary[:1]:
                sec_agent = _get_agent(sec_name)
                if sec_agent:
                    sec_agent.knowledge_context = knowledge_context
                    try:
                        sec_result = sec_agent.run(query, parameters)
                        if sec_result.get("success"):
                            sec_text = str(sec_result.get("result", ""))
                            if sec_text:
                                response_text += f"\n\n[{sec_name.title()}]: {sec_text}"
                                metadata[f"{sec_name}_data"] = sec_result.get("metadata", {})
                    except Exception:
                        pass

        # ── Memory ──
        if response_text and session_id:
            _mem.add_with_session("user", query, session_id)
            _mem.add_with_session("assistant", response_text[:500], session_id)
            try:
                _get_db_memory().store_message(session_id, "user", query)
                _get_db_memory().store_message(session_id, "assistant", response_text[:500])
            except Exception:
                pass

        _skill_lib.maybe_learn(query, response_text, primary, success, metadata)
        elapsed_ms = int((time.time() - start) * 1000)
        self._last_query = query
        return self._make_response(response_text, agent=primary, success=success, metadata=metadata, time_ms=elapsed_ms)

    def run_goal(self, description: str, context: dict = None) -> dict:
        """Run an autonomous goal through the WorkflowEngine."""
        try:
            engine = _get_workflow_engine()
            result = engine.process_goal(description, context)
            return {
                "goal_id": result.get("goal_id", ""),
                "status": result.get("status", "unknown"),
                "summary": result.get("summary", ""),
                "tasks_completed": result.get("tasks_completed", 0),
                "tasks_total": result.get("tasks_total", 0),
                "execution_time": result.get("execution_time", 0),
            }
        except Exception as e:
            logger.error("run_goal error: %s", e)
            return {"status": "error", "error": str(e)}

    def run_plan(self, goal: str, context: dict = None) -> list:
        """Plan a goal into subtasks without executing."""
        try:
            planner_fn = _get_planner()
            return planner_fn(goal, context or {})
        except Exception as e:
            logger.error("run_plan error: %s", e)
            return []

    def run_tool(self, tool_name: str, params: dict) -> dict:
        """Execute a tool by name."""
        try:
            executor = _get_tool_executor()
            return executor.execute({"agent": "tool", "goal": tool_name, "parameters": params})
        except Exception as e:
            logger.error("run_tool error: %s", e)
            return {"success": False, "error": str(e)}

    def verify_result(self, task: dict, result: dict) -> dict:
        """Verify an execution result."""
        try:
            verifier = _get_verifier()
            return verifier.verify(task, result)
        except Exception as e:
            return {"verified": False, "error": str(e)}

    def _classify(self, query: str) -> dict:
        keyword_agent = _keyword_classify(query)
        if keyword_agent != "chat":
            return {"primary_agent": keyword_agent, "secondary_agents": [], "query_for_agent": query, "parameters": {}}
        if self.use_llm_classify:
            llm_result = _llm_classify(query)
            if llm_result and llm_result.get("confidence") in ("high", "medium"):
                return llm_result
            return {"primary_agent": keyword_agent, "secondary_agents": [], "query_for_agent": query, "parameters": {}}
        else:
            return {"primary_agent": keyword_agent, "secondary_agents": [], "query_for_agent": query, "parameters": {}}

    def _make_response(self, text: str, agent: str, success: bool, metadata: dict = None, time_ms: int = 0) -> dict:
        return {"response": text, "agent": agent, "success": success, "metadata": metadata or {}, "time_ms": time_ms}

    def list_agents(self) -> list:
        result = []
        for name, path in _AGENT_CLASSES.items():
            agent = _get_agent(name)
            if agent:
                result.append({"name": name, "class": agent.name, "description": agent.description, "model": agent.model})
        # Add V3 agents
        result.append({"name": "goal", "class": "WorkflowEngine", "description": "Autonomous multi-step goal execution", "model": "provider_manager"})
        result.append({"name": "planner", "class": "PlannerAgent", "description": "LLM-powered goal decomposition", "model": "provider_manager"})
        result.append({"name": "tools", "class": "ToolExecutor", "description": "Tool-based device actions", "model": "native"})
        result.append({"name": "verifier", "class": "VerifierAgent", "description": "Execution result verification", "model": "provider_manager"})
        return result

    def get_provider_health(self) -> dict:
        return get_provider_manager().health_status()

    def get_memory_stats(self) -> dict:
        try:
            db = _get_db_memory()
            return {"database_memory": True, "vector_memory": True}
        except Exception as e:
            return {"error": str(e)}
