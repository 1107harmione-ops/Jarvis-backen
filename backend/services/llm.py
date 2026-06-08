"""
LLM Service — Provider chain with circuit breaker pattern.
Priority: Groq → Gemini → OpenRouter → LocalDeepSeek
"""
import asyncio
import time
from dataclasses import dataclass
from typing import Any, AsyncGenerator, Optional
from backend.core.config import get_settings
from backend.core.logging import log_llm_call, get_logger

logger = get_logger(__name__)


@dataclass
class ProviderStats:
    name: str
    failures: int = 0
    circuit_open: bool = False
    circuit_open_until: float = 0.0
    total_calls: int = 0
    total_tokens: int = 0
    avg_latency_ms: float = 0.0


class LLMProvider:
    """Base LLM provider with circuit breaker."""

    def __init__(self, name: str):
        self.name = name
        self.stats = ProviderStats(name=name)

    async def complete(
        self,
        messages: list[dict],
        temperature: float = 0.3,
        max_tokens: int = 1024,
    ) -> Optional[dict]:
        """Send a completion request. Returns dict with 'content' and 'tokens_used' or None."""
        raise NotImplementedError

    def _check_circuit(self) -> bool:
        """Check if circuit is open. Returns True if request should be skipped."""
        if self.stats.circuit_open:
            if time.time() > self.stats.circuit_open_until:
                self.stats.circuit_open = False
                self.stats.failures = 0
                logger.info(f"Circuit closed for {self.name}")
                return False
            return True
        return False

    def _record_failure(self):
        self.stats.failures += 1
        if self.stats.failures >= 3:
            self.stats.circuit_open = True
            self.stats.circuit_open_until = time.time() + 60
            logger.warning(f"Circuit opened for {self.name} (3 failures, 60s cooldown)")

    def _record_success(self, tokens: int, latency_ms: float):
        self.stats.total_calls += 1
        self.stats.total_tokens += tokens
        self.stats.avg_latency_ms = (
            self.stats.avg_latency_ms * (self.stats.total_calls - 1) + latency_ms
        ) / self.stats.total_calls


class GroqProvider(LLMProvider):
    def __init__(self):
        super().__init__("groq")

    async def complete(self, messages, temperature=0.3, max_tokens=1024) -> Optional[dict]:
        if self._check_circuit():
            return None
        settings = get_settings()
        if not settings.groq_api_key:
            return None

        start = time.time()
        try:
            from openai import AsyncOpenAI

            client = AsyncOpenAI(api_key=settings.groq_api_key, base_url=settings.groq_api_base)
            response = await client.chat.completions.create(
                model=settings.groq_chat_model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            latency = (time.time() - start) * 1000
            content = response.choices[0].message.content
            tokens = response.usage.total_tokens if response.usage else 0
            self._record_success(tokens, latency)
            log_llm_call("groq", settings.groq_chat_model, tokens // 2, tokens // 2, latency, True)
            return {"content": content, "tokens_used": tokens, "model": settings.groq_chat_model}
        except Exception as e:
            latency = (time.time() - start) * 1000
            self._record_failure()
            log_llm_call("groq", settings.groq_chat_model, 0, 0, latency, False, error=str(e))
            logger.warning(f"Groq completion failed: {e}")
            return None


class GeminiProvider(LLMProvider):
    def __init__(self):
        super().__init__("gemini")

    async def complete(self, messages, temperature=0.3, max_tokens=1024) -> Optional[dict]:
        if self._check_circuit():
            return None
        settings = get_settings()
        if not settings.gemini_api_key:
            return None

        start = time.time()
        try:
            import google.generativeai as genai

            genai.configure(api_key=settings.gemini_api_key)
            model = genai.GenerativeModel(settings.gemini_model)

            # Convert OpenAI-style messages to Gemini format
            prompt = ""
            for msg in messages:
                role = msg.get("role", "user")
                content = msg.get("content", "")
                if role == "system":
                    prompt += f"System: {content}\n\n"
                elif role == "user":
                    prompt += f"User: {content}\n"
                elif role == "assistant":
                    prompt += f"Assistant: {content}\n"

            response = await model.generate_content_async(prompt)
            latency = (time.time() - start) * 1000
            content = response.text
            self._record_success(len(content), latency)
            log_llm_call("gemini", settings.gemini_model, len(prompt), len(content), latency, True)
            return {"content": content, "tokens_used": len(prompt) + len(content), "model": settings.gemini_model}
        except Exception as e:
            latency = (time.time() - start) * 1000
            self._record_failure()
            log_llm_call("gemini", settings.gemini_model, 0, 0, latency, False, error=str(e))
            return None


class OpenRouterProvider(LLMProvider):
    def __init__(self):
        super().__init__("openrouter")

    async def complete(self, messages, temperature=0.3, max_tokens=1024) -> Optional[dict]:
        if self._check_circuit():
            return None
        settings = get_settings()
        if not settings.openrouter_api_key:
            return None

        start = time.time()
        try:
            from openai import AsyncOpenAI

            client = AsyncOpenAI(api_key=settings.openrouter_api_key, base_url=settings.openrouter_api_base)
            response = await client.chat.completions.create(
                model=settings.openrouter_model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            latency = (time.time() - start) * 1000
            content = response.choices[0].message.content
            tokens = response.usage.total_tokens if response.usage else 0
            self._record_success(tokens, latency)
            return {"content": content, "tokens_used": tokens, "model": settings.openrouter_model}
        except Exception as e:
            latency = (time.time() - start) * 1000
            self._record_failure()
            return None


class LLMService:
    """Main LLM service with provider fallback chain and streaming."""

    def __init__(self):
        self.settings = get_settings()
        self.providers: list[LLMProvider] = [
            GroqProvider(),
            GeminiProvider(),
            OpenRouterProvider(),
        ]
        self._current_provider_index = 0

    async def complete(
        self,
        messages: list[dict],
        temperature: float = 0.3,
        max_tokens: int = 1024,
    ) -> dict:
        """
        Get a completion from the LLM fallback chain.

        Returns:
            {"content": str, "tokens_used": int, "model": str, "provider": str}
        """
        errors = []

        for provider in self.providers:
            result = await provider.complete(messages, temperature, max_tokens)
            if result and result.get("content"):
                return {
                    **result,
                    "provider": provider.name,
                }
            errors.append(f"{provider.name}: {getattr(result, 'error', 'unavailable')}")

        # All providers failed
        error_msg = "; ".join(errors)
        logger.error(f"All LLM providers unavailable: {error_msg}")
        return {
            "content": f"I apologize, but all my language model backends are currently unavailable. Please try again later. [Errors: {error_msg}]",
            "tokens_used": 0,
            "model": "none",
            "provider": "fallback",
        }

    async def complete_stream(
        self,
        messages: list[dict],
        temperature: float = 0.3,
        max_tokens: int = 1024,
    ) -> AsyncGenerator[str, None]:
        """Stream a completion from the LLM."""
        settings = get_settings()

        if not settings.groq_api_key:
            yield "I'm sorry, but the AI backend is not configured. Please set up an API key."
            return

        try:
            from openai import AsyncOpenAI

            client = AsyncOpenAI(api_key=settings.groq_api_key, base_url=settings.groq_api_base)

            stream = await client.chat.completions.create(
                model=settings.groq_chat_model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                stream=True,
            )

            async for chunk in stream:
                if chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content

        except Exception as e:
            logger.error(f"Streaming failed: {e}")
            yield f"\n\n[Streaming error: {e}]"

    def get_stats(self) -> list[dict]:
        """Get provider statistics."""
        return [
            {
                "name": p.name,
                "total_calls": p.stats.total_calls,
                "total_tokens": p.stats.total_tokens,
                "avg_latency_ms": round(p.stats.avg_latency_ms, 1),
                "circuit_open": p.stats.circuit_open,
                "failures": p.stats.failures,
            }
            for p in self.providers
        ]


# Global instance
_llm_service: Optional[LLMService] = None


def get_llm_service() -> LLMService:
    global _llm_service
    if _llm_service is None:
        _llm_service = LLMService()
    return _llm_service
