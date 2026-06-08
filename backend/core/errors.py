"""
Custom exception classes and error handling utilities.
"""
from typing import Any, Optional


class JARVISError(Exception):
    """Base exception for all JARVIS errors."""
    def __init__(self, message: str, code: str = "internal_error", status_code: int = 500, details: Optional[dict] = None):
        self.message = message
        self.code = code
        self.status_code = status_code
        self.details = details or {}
        super().__init__(self.message)

    def to_dict(self) -> dict:
        return {
            "error": self.code,
            "message": self.message,
            "status_code": self.status_code,
            "details": self.details,
        }


class AuthenticationError(JARVISError):
    def __init__(self, message: str = "Authentication required", details: Optional[dict] = None):
        super().__init__(message, code="auth_required", status_code=401, details=details)


class AuthorizationError(JARVISError):
    def __init__(self, message: str = "Insufficient permissions", details: Optional[dict] = None):
        super().__init__(message, code="forbidden", status_code=403, details=details)


class NotFoundError(JARVISError):
    def __init__(self, resource: str = "Resource", identifier: Optional[str] = None):
        msg = f"{resource} not found" + (f": {identifier}" if identifier else "")
        super().__init__(msg, code="not_found", status_code=404)


class ValidationError(JARVISError):
    def __init__(self, message: str, details: Optional[dict] = None):
        super().__init__(message, code="validation_error", status_code=422, details=details)


class RateLimitError(JARVISError):
    def __init__(self, retry_after: int = 60):
        super().__init__(
            f"Rate limit exceeded. Try again in {retry_after}s",
            code="rate_limited",
            status_code=429,
            details={"retry_after": retry_after},
        )


class LLMProviderError(JARVISError):
    def __init__(self, provider: str, message: str):
        super().__init__(
            f"LLM provider '{provider}' error: {message}",
            code="llm_provider_error",
            status_code=503,
        )


class ToolExecutionError(JARVISError):
    def __init__(self, tool: str, message: str):
        super().__init__(
            f"Tool '{tool}' execution failed: {message}",
            code="tool_execution_error",
            status_code=500,
        )


def error_to_fastapi_response(error: JARVISError):
    """Convert a JARVISError to a FastAPI-compatible response dict."""
    from fastapi.responses import JSONResponse
    return JSONResponse(
        status_code=error.status_code,
        content=error.to_dict(),
    )
