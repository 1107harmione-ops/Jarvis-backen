import time

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from backend.core.logging import log_api_call


class LoggingMiddleware(BaseHTTPMiddleware):
    """Log every API call with method, path, status code, and duration."""

    async def dispatch(self, request: Request, call_next) -> None:  # noqa: A003
        start = time.time()
        response = await call_next(request)
        duration = time.time() - start

        log_api_call(
            endpoint=request.url.path,
            method=request.method,
            status=response.status_code,
            duration_ms=duration * 1000,
        )
