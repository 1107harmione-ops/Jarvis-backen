import json, os, re, time, requests
from core.config import GROQ_API_BASE, GROQ_CHAT_API_KEY, GROQ_CHAT_MODEL
from core.data_center import DataCenter
from core.auto_skill import SkillLibrary
from core.memory import Memory

_session = requests.Session()
_mem = Memory()
_datacenter = DataCenter()
_skill_lib = SkillLibrary()
TRAINING_DIR = "training_data"

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
- chat: general conversation, questions, advice, anything else

Return ONLY valid JSON:
{
  "primary_agent": "coding|image|task|research|search|reasoning|chat",
  "secondary_agents": [],
  "confidence": "high|medium|low",
  "query_for_agent": "<query refined for the agent>",
  "parameters": {}
}

Rules:
- Use "search" for quick lookups, "research" for detailed multi-source analysis
- Use "task" for any device/app/system control
- Use "reasoning" for math, planning, multi-step problems
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
]

def _keyword_classify(query: str) -> str:
    q = query.lower()
    for keywords, agent in _KEYWORD_ROUTES:
        if any(kw in q for kw in keywords):
            return agent
    return "chat"

def _llm_classify(query: str) -> dict:
    try:
        payload = {"model": GROQ_CHAT_MODEL, "messages": [{"role": "system", "content": CLASSIFY_SYSTEM}, {"role": "user", "content": query}], "temperature": 0.0, "max_tokens": 300}
        r = _session.post(f"{GROQ_API_BASE}/chat/completions", headers={"Authorization": f"Bearer {GROQ_CHAT_API_KEY}", "Content-Type": "application/json"}, json=payload, timeout=8)
        if r.status_code == 200:
            raw = r.json()["choices"][0]["message"]["content"]
            m = re.search(r"\{.*\}", raw, re.DOTALL)
            if m:
                return json.loads(m.group())
    except Exception:
        pass
    return {}

def _chat_response(query: str, knowledge_context: str = "", session_id: str = "") -> str:
    from core.brain import ask_llm
    enriched_query = query
    if knowledge_context:
        enriched_query = f"[Knowledge Context]\n{knowledge_context}\n\n[User Query]\n{query}"
    response = ask_llm([{"role": "user", "content": enriched_query}])
    if session_id:
        _mem.add_with_session("user", query, session_id)
        _mem.add_with_session("assistant", response, session_id)
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
            skills_text = "\n\n".join(f"[Skill: {s['name']}]\n{s['description']}\nSteps: " + "; ".join(s.get("steps", [])) for s in auto_skills)
            parameters.setdefault("knowledge_context", "")
            parameters["knowledge_context"] += f"\n\n--- RELEVANT AUTO-SKILLS ---\n{skills_text}\n--- END SKILLS ---"
        if knowledge_context:
            parameters["knowledge_context"] = knowledge_context
        print(f"[Orchestrator] '{query[:60]}' -> agent={primary}")
        if primary == "chat":
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
        if response_text:
            if session_id:
                _mem.add_with_session("user", query, session_id)
                _mem.add_with_session("assistant", response_text[:500], session_id)
            else:
                _mem.add("user", query)
                _mem.add("assistant", response_text[:500])
        _skill_lib.maybe_learn(query, response_text, primary, success, metadata)
        elapsed_ms = int((time.time() - start) * 1000)
        self._last_query = query
        return self._make_response(response_text, agent=primary, success=success, metadata=metadata, time_ms=elapsed_ms)

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
        return result
