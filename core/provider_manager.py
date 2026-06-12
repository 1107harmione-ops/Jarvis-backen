"""
provider_manager.py — Multi-LLM provider management with fallback chain.

Providers: Groq → Gemini → OpenRouter → Local DeepSeek
Features: health checks, timeout handling, circuit breaker, cost tracking
"""
import json, logging, os, time
import requests
from typing import Optional
from dataclasses import dataclass, field
from datetime import datetime

logger = logging.getLogger("provider_manager")


@dataclass
class ProviderStats:
    name: str
    success_count: int = 0
    failure_count: int = 0
    total_latency_ms: float = 0
    last_error: str = ""
    last_used: float = 0
    circuit_open: bool = False
    circuit_retry_at: float = 0
    # Track consecutive failures (not cumulative) for circuit breaker
    consecutive_failures: int = 0


class Provider:
    """Base LLM provider interface."""

    def __init__(self, name: str, api_key: str, base_url: str, model: str,
                 priority: int = 10):
        self.name = name
        self.api_key = api_key
        self.base_url = base_url
        self.model = model
        self.priority = priority
        self.stats = ProviderStats(name=name)
        self._session = None

    @property
    def session(self):
        if self._session is None:
            import requests
            self._session = requests.Session()
            self._session.headers.update({"Content-Type": "application/json"})
        return self._session

    def complete(self, messages: list, temperature: float = 0.3,
                 max_tokens: int = 1024) -> Optional[str]:
        """Send a completion request. Returns text or None on failure."""
        raise NotImplementedError

    def health_check(self) -> bool:
        """Check if the provider is reachable."""
        raise NotImplementedError

    def _update_stats(self, success: bool, latency_ms: float = 0,
                      error: str = ""):
        self.stats.last_used = time.time()
        if success:
            self.stats.success_count += 1
            self.stats.total_latency_ms += latency_ms
            self.stats.consecutive_failures = 0   # reset on success
        else:
            self.stats.failure_count += 1
            self.stats.consecutive_failures += 1
            self.stats.last_error = error

    def __repr__(self):
        return f"<Provider {self.name} ({self.model}) prio={self.priority}>"


class GroqProvider(Provider):
    def __init__(self):
        super().__init__(
            name="groq",
            api_key=os.environ.get("GROQ_CHAT_API_KEY", ""),
            base_url=os.environ.get("GROQ_API_BASE", "https://api.groq.com/openai/v1"),
            model=os.environ.get("GROQ_CHAT_MODEL", "llama-3.1-8b-instant"),
            priority=1,
        )

    def complete(self, messages, temperature=0.3, max_tokens=1024):
        if not self.api_key:
            return None
        start = time.time()
        try:
            url = f"{self.base_url.rstrip('/')}/chat/completions"
            payload = {"model": self.model, "messages": messages,
                       "temperature": temperature, "max_tokens": max_tokens}
            r = self.session.post(url, json=payload,
                                  headers={"Authorization": f"Bearer {self.api_key}"},
                                  timeout=15)
            if r.status_code == 200:
                text = r.json()["choices"][0]["message"]["content"].strip()
                self._update_stats(True, (time.time() - start) * 1000)
                return text
            self._update_stats(False, error=f"HTTP {r.status_code}")
            return None
        except Exception as e:
            self._update_stats(False, error=str(e))
            return None

    def health_check(self) -> bool:
        if not self.api_key:
            return False
        try:
            r = self.session.get(
                f"{self.base_url.rstrip('/')}/models",
                headers={"Authorization": f"Bearer {self.api_key}"},
                timeout=5
            )
            return r.status_code == 200
        except Exception:
            return False


class GeminiProvider(Provider):
    def __init__(self):
        super().__init__(
            name="gemini",
            api_key=os.environ.get("GEMINI_API_KEY", ""),
            base_url="https://generativelanguage.googleapis.com/v1beta",
            model=os.environ.get("GEMINI_MODEL", "gemini-2.0-flash"),
            priority=2,
        )

    def complete(self, messages, temperature=0.3, max_tokens=1024):
        if not self.api_key:
            return None
        start = time.time()
        try:
            contents = []
            for m in messages:
                role = "user" if m["role"] in ("user", "system") else "model"
                contents.append({"role": role, "parts": [{"text": m["content"]}]})
            url = f"{self.base_url}/models/{self.model}:generateContent?key={self.api_key}"
            payload = {"contents": contents,
                       "generationConfig": {"temperature": temperature,
                                            "maxOutputTokens": max_tokens}}
            r = self.session.post(url, json=payload, timeout=15)
            if r.status_code == 200:
                data = r.json()
                parts = data.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])
                text = parts[0].get("text", "").strip() if parts else ""
                self._update_stats(True, (time.time() - start) * 1000)
                return text or None
            self._update_stats(False, error=f"HTTP {r.status_code}")
            return None
        except Exception as e:
            self._update_stats(False, error=str(e))
            return None

    def health_check(self) -> bool:
        """Actually test connectivity to Gemini API."""
        if not self.api_key:
            return False
        try:
            url = f"{self.base_url}/models?key={self.api_key}"
            r = self.session.get(url, timeout=5)
            return r.status_code == 200
        except Exception:
            return False


class OpenRouterProvider(Provider):
    def __init__(self):
        super().__init__(
            name="openrouter",
            api_key=os.environ.get("OPENROUTER_API_KEY", ""),
            base_url="https://openrouter.ai/api/v1",
            model=os.environ.get("OPENROUTER_MODEL", "mistralai/mixtral-8x7b-instruct"),
            priority=3,
        )

    def complete(self, messages, temperature=0.3, max_tokens=1024):
        if not self.api_key:
            return None
        start = time.time()
        try:
            url = f"{self.base_url.rstrip('/')}/chat/completions"
            payload = {"model": self.model, "messages": messages,
                       "temperature": temperature, "max_tokens": max_tokens}
            r = self.session.post(url, json=payload,
                                  headers={"Authorization": f"Bearer {self.api_key}",
                                           "HTTP-Referer": "https://jarvis.local"},
                                  timeout=15)
            if r.status_code == 200:
                text = r.json()["choices"][0]["message"]["content"].strip()
                self._update_stats(True, (time.time() - start) * 1000)
                return text
            self._update_stats(False, error=f"HTTP {r.status_code}")
            return None
        except Exception as e:
            self._update_stats(False, error=str(e))
            return None

    def health_check(self) -> bool:
        """Actually test connectivity to OpenRouter API."""
        if not self.api_key:
            return False
        try:
            r = self.session.get(
                f"{self.base_url.rstrip('/')}/models",
                headers={"Authorization": f"Bearer {self.api_key}"},
                timeout=5
            )
            return r.status_code == 200
        except Exception:
            return False


class LocalDeepSeekProvider(Provider):
    def __init__(self):
        super().__init__(
            name="local",
            api_key="not-needed",
            base_url=os.environ.get("LOCAL_LLM_URL", "http://localhost:8000/v1"),
            model=os.environ.get("LOCAL_LLM_MODEL", "deepseek-coder-6.7b-instruct"),
            priority=4,
        )

    def complete(self, messages, temperature=0.3, max_tokens=1024):
        start = time.time()
        try:
            url = f"{self.base_url.rstrip('/')}/chat/completions"
            payload = {"model": self.model, "messages": messages,
                       "temperature": temperature, "max_tokens": max_tokens}
            r = self.session.post(url, json=payload, timeout=30)
            if r.status_code == 200:
                text = r.json()["choices"][0]["message"]["content"].strip()
                self._update_stats(True, (time.time() - start) * 1000)
                return text
            self._update_stats(False, error=f"HTTP {r.status_code}")
            return None
        except requests.exceptions.ConnectionError:
            self._update_stats(False, error="Connection refused")
            return None
        except Exception as e:
            self._update_stats(False, error=str(e))
            return None

    def health_check(self) -> bool:
        try:
            r = requests.get(f"{self.base_url.rstrip('/')}/models", timeout=3)
            return r.status_code == 200
        except Exception:
            return False


class ProviderManager:
    """Manages LLM providers with fallback chain and circuit breaker."""

    # Open circuit after this many CONSECUTIVE failures (not cumulative)
    _CIRCUIT_OPEN_THRESHOLD = 3
    _CIRCUIT_BREAKER_TIMEOUT = 60  # seconds before retrying a failed provider

    def __init__(self):
        self.providers: list[Provider] = []
        self._init_providers()

    def _init_providers(self):
        candidates = [
            GroqProvider(),
            GeminiProvider(),
            OpenRouterProvider(),
            LocalDeepSeekProvider(),
        ]
        # Only include providers with valid config
        self.providers = [p for p in candidates if p.api_key or p.name == "local"]
        logger.info("ProviderManager: %d providers loaded: %s",
                    len(self.providers), [p.name for p in self.providers])

    def complete(self, messages: list, temperature: float = 0.3,
                 max_tokens: int = 1024, model: Optional[str] = None) -> str:
        """Try providers in priority order until one succeeds."""
        errors = []
        for provider in self.providers:
            # Circuit breaker check
            if provider.stats.circuit_open:
                if time.time() < provider.stats.circuit_retry_at:
                    errors.append(f"{provider.name}: circuit open")
                    continue
                provider.stats.circuit_open = False  # half-open: allow one attempt
                provider.stats.consecutive_failures = 0

            # Model filter: skip if a specific model was requested and doesn't match
            if model and model != provider.model:
                continue

            result = provider.complete(messages, temperature, max_tokens)
            if result:
                return result

            errors.append(f"{provider.name}: {provider.stats.last_error}")

            # Open circuit based on CONSECUTIVE failures
            if (not provider.stats.circuit_open and
                    provider.stats.consecutive_failures >= self._CIRCUIT_OPEN_THRESHOLD):
                provider.stats.circuit_open = True
                provider.stats.circuit_retry_at = time.time() + self._CIRCUIT_BREAKER_TIMEOUT
                logger.warning("Circuit opened for %s (retry at %.0f)",
                               provider.name, provider.stats.circuit_retry_at)

        # All providers failed
        logger.error("All LLM providers failed: %s", "; ".join(errors))
        return f"[All LLM providers unavailable. Errors: {'; '.join(errors[-3:])}]"

    def health_status(self) -> dict:
        status = {}
        for p in self.providers:
            try:
                healthy = p.health_check()
            except Exception:
                healthy = False
            status[p.name] = {
                "healthy": healthy,
                "model": p.model,
                "circuit_open": p.stats.circuit_open,
                "success_count": p.stats.success_count,
                "failure_count": p.stats.failure_count,
                "avg_latency_ms": round(
                    p.stats.total_latency_ms / max(p.stats.success_count, 1), 1
                ),
            }
        return status

    def get_provider_stats(self) -> list:
        return [{
            "name": p.name,
            "model": p.model,
            "priority": p.priority,
            "success_count": p.stats.success_count,
            "failure_count": p.stats.failure_count,
            "consecutive_failures": p.stats.consecutive_failures,
            "circuit_open": p.stats.circuit_open,
        } for p in self.providers]


# Global singleton
_provider_manager = ProviderManager()


def llm_completion(messages: list, system: str = None, temperature: float = 0.3,
                   max_tokens: int = 1024, model: str = None) -> str:
    """Convenience function: complete with provider manager."""
    msgs = list(messages)
    if system:
        msgs.insert(0, {"role": "system", "content": system})
    return _provider_manager.complete(msgs, temperature, max_tokens, model)


def get_provider_manager() -> ProviderManager:
    return _provider_manager
