from fastapi import Request

from backend.core.config import get_settings


async def rate_limiter(request: Request) -> str:
    """Simple in-memory rate limiter as fallback before Redis is available.

    Returns the client IP address. The actual Redis-based rate limiter
    will be integrated later.
    """
    settings = get_settings()  # noqa: F841 — kept for future Redis integration
    client_ip = request.client.host if request.client else "unknown"
    # If Redis is available, use it; otherwise use simple in-memory
    # For now, just pass through (Redis integration will be added)
    return client_ip
