"""
JARVIS V3 — Pydantic Settings
Environment-aware configuration with validation & secrets management.
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Core ──────────────────────────────────────────────────────────
    app_name: str = "JARVIS V3"
    debug: bool = False
    log_level: str = Field(default="INFO", pattern=r"^(DEBUG|INFO|WARNING|ERROR|CRITICAL)$")
    secret_key: str = Field(default="change-me-to-a-random-64-char-string", min_length=16)
    environment: str = Field(default="development", pattern=r"^(development|staging|production)$")

    # ── Server ────────────────────────────────────────────────────────
    host: str = "0.0.0.0"
    port: int = Field(default=8001, ge=1, le=65535)
    workers: int = Field(default=4, ge=1, le=32)
    max_connections: int = Field(default=1000, ge=1)

    # ── Database ──────────────────────────────────────────────────────
    database_url: str = Field(
        default="postgresql+asyncpg://jarvis:jarvis@localhost:5432/jarvis"
    )
    database_pool_size: int = Field(default=20, ge=1)
    database_max_overflow: int = Field(default=40, ge=1)
    database_echo: bool = False

    # ── Redis ─────────────────────────────────────────────────────────
    redis_url: str = Field(default="redis://localhost:6379/0")
    redis_password: Optional[str] = None
    redis_socket_timeout: int = Field(default=5, ge=1)
    redis_socket_connect_timeout: int = Field(default=5, ge=1)

    # ── JWT ───────────────────────────────────────────────────────────
    jwt_secret: str = Field(default="change-me-to-a-random-64-char-string", min_length=16)
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = Field(default=30, ge=1)
    refresh_token_expire_days: int = Field(default=7, ge=1)

    # ── LLM Providers ─────────────────────────────────────────────────
    groq_api_key: Optional[str] = None
    groq_api_base: str = "https://api.groq.com/openai/v1"
    groq_chat_model: str = "llama-3.1-8b-instant"

    openai_api_key: Optional[str] = None
    openai_api_base: str = "https://api.openai.com/v1"
    openai_chat_model: str = "gpt-4o-mini"

    openrouter_api_key: Optional[str] = None
    openrouter_api_base: str = "https://openrouter.ai/api/v1"
    openrouter_model: str = "mistralai/mixtral-8x7b-instruct"

    gemini_api_key: Optional[str] = None
    gemini_model: str = "gemini-2.0-flash"

    local_llm_url: str = "http://localhost:8000/v1"
    local_llm_model: str = "deepseek-coder-6.7b-instruct"

    # ── Speech-to-Text ────────────────────────────────────────────────
    whisper_model_size: str = "tiny"
    whisper_model_dir: str = "data/faster_whisper_models"
    stt_fallback_chain: str = "faster-whisper,lite,vosk"

    # ── Text-to-Speech ────────────────────────────────────────────────
    tts_engine: str = "espeak"
    tts_voice: str = "en-us"
    tts_speed: int = Field(default=160, ge=80, le=500)

    # ── Rate Limiting ─────────────────────────────────────────────────
    rate_limit_per_ip: int = Field(default=60, ge=1)
    rate_limit_per_user: int = Field(default=120, ge=1)
    rate_limit_window: int = Field(default=60, ge=1)
    rate_limit_burst: int = Field(default=10, ge=1)

    # ── WebSocket ─────────────────────────────────────────────────────
    ws_max_connections: int = Field(default=1000, ge=1)
    ws_heartbeat_interval: int = Field(default=30, ge=5)
    ws_max_idle_time: int = Field(default=300, ge=30)

    # ── Security ──────────────────────────────────────────────────────
    cors_origins: str = "http://localhost:3000,https://jarvis.app"
    shutdown_token: Optional[str] = None
    enforce_https: bool = False
    max_upload_size: int = Field(default=10_485_760, ge=1)

    # ── MCP ───────────────────────────────────────────────────────────
    mcp_github_token: Optional[str] = None
    mcp_browser_headless: bool = True
    mcp_filesystem_root: str = "/data/mcp"

    # ── Monitoring ────────────────────────────────────────────────────
    otel_service_name: str = "jarvis-v3"
    otel_exporter_otlp_endpoint: str = "http://localhost:4318"
    sentry_dsn: Optional[str] = None

    # ── Android ───────────────────────────────────────────────────────
    android_fcm_server_key: Optional[str] = None
    android_package_name: str = "com.jarvis.assistant"

    # ── Feature Flags ─────────────────────────────────────────────────
    enable_voice: bool = True
    enable_mcp: bool = True
    enable_goals: bool = True
    enable_tools: bool = True
    enable_auto_skills: bool = True
    enable_telemetry: bool = False

    # ── Validators ────────────────────────────────────────────────────

    @field_validator("cors_origins")
    @classmethod
    def parse_cors_origins(cls, v: str) -> list[str]:
        """Parse comma-separated CORS origins into a list."""
        return [origin.strip() for origin in v.split(",") if origin.strip()]

    @field_validator("secret_key", "jwt_secret")
    @classmethod
    def warn_default_secrets(cls, v: str) -> str:
        """Warn if default secrets are used in production."""
        if v in ("change-me", "change-me-to-a-random-64-char-string"):
            import warnings
            warnings.warn(
                f"Using default secret key in {os.getenv('ENVIRONMENT', 'unknown')} mode. "
                "Set a strong random value in .env for production."
            )
        return v

    @property
    def stt_fallback_list(self) -> list[str]:
        """Parse comma-separated STT fallback chain."""
        return [s.strip() for s in self.stt_fallback_chain.split(",") if s.strip()]

    @property
    def is_production(self) -> bool:
        return self.environment == "production"


@lru_cache()
def get_settings() -> Settings:
    """Return cached singleton Settings instance."""
    return Settings()


def reload_settings() -> Settings:
    """Force reload settings (useful for testing)."""
    get_settings.cache_clear()
    return get_settings()
