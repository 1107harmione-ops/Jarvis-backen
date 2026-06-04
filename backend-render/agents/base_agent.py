import json
import re
import time
import requests
from abc import ABC, abstractmethod
from core.config import GROQ_API_BASE, GROQ_CHAT_API_KEY, GROQ_CHAT_MODEL

_session = requests.Session()

class BaseAgent(ABC):
    name: str = "BaseAgent"
    description: str = "Base agent"
    model: str = GROQ_CHAT_MODEL
    max_tokens: int = 2048
    temperature: float = 0.3
    knowledge_context: str = ""

    @abstractmethod
    def run(self, query: str, parameters: dict = None) -> dict:
        raise NotImplementedError

    def _ask(self, messages: list, system: str = None, model: str = None, temperature: float = None, max_tokens: int = None) -> str:
        mdl = model or self.model
        temp = temperature if temperature is not None else self.temperature
        mtok = max_tokens or self.max_tokens
        payload_msgs = []
        if system:
            enriched = system
            if self.knowledge_context:
                enriched += f"\n\nRelevant Knowledge:\n{self.knowledge_context}"
            payload_msgs.append({"role": "system", "content": enriched})
        elif self.knowledge_context:
            payload_msgs.append({"role": "system", "content": f"Relevant Knowledge:\n{self.knowledge_context}"})
        payload_msgs.extend(messages)
        payload = {"model": mdl, "messages": payload_msgs, "temperature": temp, "max_tokens": mtok}
        try:
            r = _session.post(f"{GROQ_API_BASE}/chat/completions",
                headers={"Authorization": f"Bearer {GROQ_CHAT_API_KEY}", "Content-Type": "application/json"},
                json=payload, timeout=30)
            if r.status_code == 200:
                return r.json()["choices"][0]["message"]["content"].strip()
            return f"[LLM error {r.status_code}]"
        except Exception as e:
            return f"[LLM connection error: {e}]"

    def _ask_json(self, messages: list, system: str = None, model: str = None) -> dict:
        raw = self._ask(messages, system=system, model=model, temperature=0.0)
        try:
            m = re.search(r"\{.*\}", raw, re.DOTALL)
            if m:
                return json.loads(m.group())
        except Exception:
            pass
        return {}

    def _ok(self, result, metadata: dict = None) -> dict:
        return {"agent": self.name, "success": True, "result": result, "metadata": metadata or {}}

    def _err(self, message: str) -> dict:
        return {"agent": self.name, "success": False, "result": message, "metadata": {}}

    def __repr__(self):
        return f"<{self.name}: {self.description}>"
