import json
import re
import time
import logging
from abc import ABC, abstractmethod
from core.provider_manager import llm_completion

logger = logging.getLogger("base_agent")


class BaseAgent(ABC):
    name: str = "BaseAgent"
    description: str = "Base agent"
    model: str = ""          # empty → ProviderManager picks best available
    max_tokens: int = 2048
    temperature: float = 0.3
    knowledge_context: str = ""

    @abstractmethod
    def run(self, query: str, parameters: dict = None) -> dict:
        raise NotImplementedError

    def _ask(self, messages: list, system: str = None, model: str = None,
             temperature: float = None, max_tokens: int = None) -> str:
        """Route LLM request through ProviderManager for full fallback support."""
        temp = temperature if temperature is not None else self.temperature
        mtok = max_tokens or self.max_tokens
        mdl = model or self.model or None   # None → ProviderManager chooses

        # Build system prompt, optionally enriched with knowledge context
        effective_system = system or ""
        if self.knowledge_context:
            if effective_system:
                effective_system += f"\n\nRelevant Knowledge:\n{self.knowledge_context}"
            else:
                effective_system = f"Relevant Knowledge:\n{self.knowledge_context}"

        try:
            result = llm_completion(
                messages,
                system=effective_system or None,
                temperature=temp,
                max_tokens=mtok,
                model=mdl,
            )
            return result
        except Exception as e:
            logger.error("BaseAgent._ask error: %s", e)
            return f"[LLM connection error: {e}]"

    def _ask_json(self, messages: list, system: str = None, model: str = None) -> dict:
        """Ask LLM expecting a JSON response; returns empty dict on failure."""
        raw = self._ask(messages, system=system, model=model, temperature=0.0)
        try:
            m = re.search(r"\{.*\}", raw, re.DOTALL)
            if m:
                return json.loads(m.group())
        except Exception:
            pass
        return {}

    def _ok(self, result, metadata: dict = None) -> dict:
        return {"agent": self.name, "success": True, "result": result,
                "metadata": metadata or {}}

    def _err(self, message: str) -> dict:
        return {"agent": self.name, "success": False, "result": message,
                "metadata": {}}

    def __repr__(self):
        return f"<{self.name}: {self.description}>"
