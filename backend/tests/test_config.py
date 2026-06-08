"""Tests for Pydantic settings."""
import os
import pytest
from backend.core.config import get_settings, reload_settings


class TestSettings:
    def test_default_values(self):
        settings = get_settings()
        assert settings.app_name == "JARVIS V3"
        assert settings.port == 8001
        assert settings.log_level == "INFO"

    def test_env_override(self):
        os.environ["APP_NAME"] = "Test JARVIS"
        os.environ["PORT"] = "9999"
        reload_settings()
        settings = get_settings()
        assert settings.app_name == "Test JARVIS"
        assert settings.port == 9999
        # Cleanup
        del os.environ["APP_NAME"]
        del os.environ["PORT"]
        reload_settings()

    def test_cors_origins_parsing(self):
        os.environ["CORS_ORIGINS"] = "http://a.com,http://b.com"
        reload_settings()
        settings = get_settings()
        assert isinstance(settings.cors_origins, list)
        assert "http://a.com" in settings.cors_origins
        assert "http://b.com" in settings.cors_origins
        del os.environ["CORS_ORIGINS"]
        reload_settings()

    def test_stt_fallback_list(self):
        os.environ["STT_FALLBACK_CHAIN"] = "whisper,lite,vosk"
        reload_settings()
        settings = get_settings()
        assert settings.stt_fallback_list == ["whisper", "lite", "vosk"]
        del os.environ["STT_FALLBACK_CHAIN"]
        reload_settings()

    def test_is_production(self):
        os.environ["ENVIRONMENT"] = "production"
        reload_settings()
        settings = get_settings()
        assert settings.is_production
        del os.environ["ENVIRONMENT"]
        reload_settings()

    def test_is_not_production(self):
        settings = get_settings()
        assert not settings.is_production
