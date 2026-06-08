import time

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from backend.core.logging import log_security_event


class SecurityMiddleware(BaseHTTPMiddleware):
    """Add security headers to every response and log slow requests.

    Headers applied:
        - X-Content-Type-Options: nosniff
        - X-Frame-Options: DENY
        - X-XSS-Protection: 1; mode=block
        - Strict-Transport-Security (HSTS)
        - Referrer-Policy: strict-origin-when-cross-origin
    """

    async def dispatch(self, request: Request, call_next) -> Response:  # noqa: A003
        start = time.time()

        response = await call_next(request)

        # ── Security headers ──────────────────────────────────────
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Strict-Transport-Security"] = (
            "max-age=31536000; includeSubDomains"
        )
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

        # ── Log slow requests (>5s) ───────────────────────────────
        duration = time.time() - start
        if duration > 5:
            log_security_event(
                "slow_request",
                severity="warning",
                path=request.url.path,
                duration=round(duration, 2),
            )

        return response
