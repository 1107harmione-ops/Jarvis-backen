"""
JARVIS V3 — Backend Package
Production-ready voice assistant backend with FastAPI, PostgreSQL, Redis, WebSockets.
"""

__version__ = "3.0.0"
__app_name__ = "JARVIS V3"

from backend.core.config import get_settings
from backend.core.logging import setup_logging

# Initialize logging on import
settings = get_settings()
setup_logging(level=settings.log_level)
