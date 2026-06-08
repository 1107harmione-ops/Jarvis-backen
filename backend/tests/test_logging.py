"""Tests for logging module."""
import pytest
from backend.core.logging import (
    setup_logging,
    log_api_call,
    log_llm_call,
    log_ws_event,
    log_security_event,
)


class TestLogging:
    def test_setup_logging(self):
        """Test that logging setup doesn't crash."""
        setup_logging(level="DEBUG")

    def test_setup_logging_with_file(self, tmp_path):
        log_file = tmp_path / "test.log"
        setup_logging(level="DEBUG", log_file=str(log_file))
        assert log_file.exists()

    def test_log_api_call(self):
        """Test API call logging doesn't crash."""
        log_api_call("/test", "GET", 200, 12.34)

    def test_log_llm_call(self):
        """Test LLM call logging doesn't crash."""
        log_llm_call("groq", "llama-3.1", 100, 50, 1234.5, True)

    def test_log_ws_event(self):
        """Test WS event logging doesn't crash."""
        log_ws_event("connect", "client123")

    def test_log_security_event(self):
        """Test security event logging doesn't crash."""
        log_security_event("auth_failure", severity="warning", ip="192.168.1.1")
