"""
JARVIS V3 — Structured Logging
Loguru-based with OpenTelemetry integration for production observability.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Optional

from loguru import logger


class InterceptHandler(logging.Handler):
    """Redirect standard logging to Loguru."""

    def emit(self, record: logging.LogRecord) -> None:
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        frame, depth = sys._getframe(6), 6
        while frame and frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1

        logger.opt(depth=depth, exception=record.exc_info).log(
            level, record.getMessage()
        )


def setup_logging(
    level: str = "INFO",
    log_file: Optional[str] = None,
    json_format: bool = False,
    service_name: str = "jarvis-v3",
) -> None:
    """
    Configure Loguru with structured output.

    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Optional file path for persistent logs
        json_format: Use JSON serialization for log output
        service_name: Service name for OpenTelemetry traces
    """
    # Remove default handler
    logger.remove()

    fmt = (
        "{time:YYYY-MM-DD HH:mm:ss.SSS} | {level:<7} | {name}:{function}:{line} | {message}"
    )
    if json_format:
        fmt = (
            '{{"timestamp":"{time:YYYY-MM-DD HH:mm:ss.SSS}",'
            '"level":"{level}",'
            '"logger":"{name}",'
            '"function":"{function}",'
            '"line":{line},'
            '"message":"{message}",'
            '"extra":{extra}}}'
        )

    # Console handler
    logger.add(
        sys.stdout,
        format=fmt,
        level=level,
        colorize=not json_format,
        backtrace=True,
        diagnose=True,
    )

    # File handler (if requested)
    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        logger.add(
            str(log_path),
            format=fmt,
            level=level,
            rotation="100 MB",
            retention="30 days",
            compression="gz",
            backtrace=True,
        )

    # Intercept standard library logging
    logging.basicConfig(handlers=[InterceptHandler()], level=0, force=True)

    logger.info(f"Logging configured | level={level} | json={json_format} | service={service_name}")


# ── Structured Logging Helpers ─────────────────────────────────

def log_api_call(endpoint: str, method: str, status: int, duration_ms: float, **kwargs) -> None:
    """Log an API call with structured context."""
    logger.bind(api=True, endpoint=endpoint, method=method, status=status, duration_ms=round(duration_ms, 2), **kwargs).info(
        f"{method} {endpoint} → {status} ({duration_ms:.1f}ms)"
    )


def log_llm_call(
    provider: str,
    model: str,
    tokens_in: int,
    tokens_out: int,
    duration_ms: float,
    success: bool,
    **kwargs,
) -> None:
    """Log an LLM provider call."""
    logger.bind(
        llm=True, provider=provider, model=model,
        tokens_in=tokens_in, tokens_out=tokens_out,
        duration_ms=round(duration_ms, 2), success=success, **kwargs,
    ).info(
        f"LLM {provider}/{model} | tokens={tokens_in}→{tokens_out} | {duration_ms:.1f}ms | {'✓' if success else '✗'}"
    )


def log_ws_event(event: str, client_id: str, **kwargs) -> None:
    """Log a WebSocket event."""
    logger.bind(ws=True, event=event, client_id=client_id, **kwargs).info(
        f"WS [{client_id[:8]}] {event}"
    )


def log_security_event(event: str, severity: str = "info", **kwargs) -> None:
    """Log a security-related event."""
    logger.bind(security=True, event=event, severity=severity, **kwargs).log(
        severity.upper() if severity.upper() in ("INFO", "WARNING", "ERROR", "CRITICAL") else "INFO",
        f"SECURITY [{severity.upper()}] {event}"
    )


# ── OpenTelemetry Integration ──────────────────────────────────

try:
    from opentelemetry import trace
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor

    _OTEL_AVAILABLE = True
except ImportError:
    _OTEL_AVAILABLE = False


def setup_opentelemetry(
    service_name: str = "jarvis-v3",
    endpoint: Optional[str] = None,
    app=None,
) -> None:
    """Initialize OpenTelemetry tracing."""
    if not _OTEL_AVAILABLE:
        logger.warning("OpenTelemetry packages not installed — skipping tracing setup")
        return

    if not endpoint:
        from backend.core.config import get_settings
        endpoint = get_settings().otel_exporter_otlp_endpoint

    resource = Resource.create({"service.name": service_name})
    provider = TracerProvider(resource=resource)
    exporter = OTLPSpanExporter(endpoint=endpoint)
    provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)

    if app is not None:
        FastAPIInstrumentor.instrument_app(app)

    logger.info(f"OpenTelemetry initialized | endpoint={endpoint} | service={service_name}")


# ── Convenience ────────────────────────────────────────────────

def get_logger(name: str):
    """Get a child logger with a bound name."""
    return logger.bind(module=name)


__all__ = [
    "setup_logging",
    "setup_opentelemetry",
    "log_api_call",
    "log_llm_call",
    "log_ws_event",
    "log_security_event",
    "get_logger",
    "logger",
]
