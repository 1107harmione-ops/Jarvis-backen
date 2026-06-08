import time
import inspect
from typing import Any, Callable, Optional
from dataclasses import dataclass, field
from backend.core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class ToolSpec:
    """Specification metadata for a registered tool."""
    name: str
    description: str
    parameters: dict[str, Any]
    category: str = "general"
    timeout: int = 30
    requires_auth: bool = False
    requires_confirmation: bool = False


@dataclass
class ToolResult:
    """Result container for tool execution."""
    success: bool
    data: Any = None
    error: Optional[str] = None
    duration_ms: float = 0.0

    def to_dict(self) -> dict:
        return {
            "success": self.success,
            "data": self.data,
            "error": self.error,
            "duration_ms": round(self.duration_ms, 2),
        }


class ToolRegistry:
    """Central registry for all executable tools.

    Tools are registered via the ``register`` decorator and can be
    invoked by name through ``execute``.  The registry doubles as a
    whitelist — only functions explicitly decorated here are callable.
    """

    def __init__(self):
        self._tools: dict[str, tuple[ToolSpec, Callable]] = {}

    def register(
        self,
        name: str,
        description: str,
        parameters: dict | None = None,
        category: str = "general",
        timeout: int = 30,
        requires_auth: bool = False,
        requires_confirmation: bool = False,
    ):
        """Decorator that registers a function as an executable tool.

        Parameters
        ----------
        name : str
            Unique tool identifier used when calling ``execute``.
        description : str
            Human-readable description exposed to LLMs and the MCP layer.
        parameters : dict | None
            JSON Schema fragment describing accepted arguments.
        category : str
            Logical grouping (e.g. ``"system"``, ``"filesystem"``, ``"web"``).
        timeout : int
            Maximum execution time in seconds.
        requires_auth : bool
            When *True* the caller must be authenticated.
        requires_confirmation : bool
            When *True* the caller must explicitly confirm before execution.
        """
        def decorator(func: Callable):
            spec = ToolSpec(
                name=name,
                description=description,
                parameters=parameters or {},
                category=category,
                timeout=timeout,
                requires_auth=requires_auth,
                requires_confirmation=requires_confirmation,
            )
            self._tools[name] = (spec, func)
            logger.debug(f"Registered tool: {name} ({category})")
            return func
        return decorator

    async def execute(
        self,
        name: str,
        args: dict[str, Any],
        user_id: str | None = None,
    ) -> ToolResult:
        """Execute a registered tool by name with the given arguments.

        Parameters
        ----------
        name : str
            Tool name as passed to ``register``.
        args : dict[str, Any]
            Keyword arguments forwarded to the underlying function.
        user_id : str | None
            Optional caller identity for audit / auth checks.

        Returns
        -------
        ToolResult
            Outcome container with ``success`` flag, ``data`` or ``error``,
            and wall-clock ``duration_ms``.
        """
        entry = self._tools.get(name)
        if not entry:
            return ToolResult(success=False, error=f"Unknown tool: {name}")

        spec, func = entry

        # ── auth guard ──────────────────────────────────────────────
        if spec.requires_auth and not user_id:
            return ToolResult(
                success=False,
                error=f"Tool '{name}' requires authentication",
            )

        start = time.time()
        try:
            if inspect.iscoroutinefunction(func):
                result = await func(**args)
            else:
                result = func(**args)

            duration = (time.time() - start) * 1000
            logger.info(f"Tool '{name}' executed in {duration:.1f}ms")
            return ToolResult(success=True, data=result, duration_ms=duration)

        except Exception as e:
            duration = (time.time() - start) * 1000
            logger.error(f"Tool '{name}' failed: {e}")
            return ToolResult(success=False, error=str(e), duration_ms=duration)

    def list_tools(self, category: str | None = None) -> list[dict]:
        """Return metadata for every registered tool, optionally filtered.

        Each entry contains the fields from ``ToolSpec`` serialised as a
        plain dict, suitable for API responses or LLM function-calling
        schemas.
        """
        tools = []
        for name, (spec, _) in self._tools.items():
            if category is None or spec.category == category:
                tools.append({
                    "name": spec.name,
                    "description": spec.description,
                    "parameters": spec.parameters,
                    "category": spec.category,
                    "timeout": spec.timeout,
                    "requires_auth": spec.requires_auth,
                    "requires_confirmation": spec.requires_confirmation,
                })
        return tools

    def get_tool(self, name: str) -> ToolSpec | None:
        """Look up a tool's specification by name, or *None* if unknown."""
        entry = self._tools.get(name)
        return entry[0] if entry else None

    @property
    def count(self) -> int:
        """Number of currently registered tools."""
        return len(self._tools)
