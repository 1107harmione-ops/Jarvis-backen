"""MCP (Model Context Protocol) server for JARVIS.

The :class:`MCPServer` exposes tools registered in the
:class:`~backend.tools.registry.ToolRegistry` as MCP-compatible
resources that LLM hosts (Claude Desktop, Cursor, etc.) can discover
and invoke remotely.
"""
import asyncio
from typing import Any, Callable, Optional

from backend.core.logging import get_logger

logger = get_logger(__name__)

# Global singleton — initialised lazily by :func:`get_mcp_server`.
_mcp_server: Optional["MCPServer"] = None


class MCPServer:
    """MCP Server for JARVIS.

    Manages a collection of tool and resource handlers that conform to
    the `Model Context Protocol`_ specification.

    .. _Model Context Protocol:
       https://modelcontextprotocol.io/
    """

    def __init__(self) -> None:
        self._tools: dict[str, dict[str, Any]] = {}
        self._resources: dict[str, dict[str, Any]] = {}
        self._is_running = False

    # ── Lifecycle ──────────────────────────────────────────────────

    async def start(self) -> None:
        """Start the MCP server (flags as ready)."""
        self._is_running = True
        logger.info("MCP Server started")

    async def stop(self) -> None:
        """Gracefully stop the MCP server."""
        self._is_running = False
        logger.info("MCP Server stopped")

    # ── Tool Registration ──────────────────────────────────────────

    def register_tool(
        self,
        name: str,
        description: str,
        input_schema: dict[str, Any],
        handler: Callable,
    ) -> None:
        """Register a callable as an MCP-exposed tool.

        Parameters
        ----------
        name : str
            Tool identifier used by the LLM when calling.
        description : str
            Prompt-friendly description of what the tool does.
        input_schema : dict
            JSON Schema describing the expected arguments.
        handler : Callable
            Async or sync function that implements the tool.
        """
        self._tools[name] = {
            "name": name,
            "description": description,
            "inputSchema": input_schema,
            "handler": handler,
        }
        logger.debug(f"MCP tool registered: {name}")

    def register_resource(
        self,
        uri: str,
        name: str,
        description: str,
        handler: Callable,
    ) -> None:
        """Register a static or templated resource URI.

        Resources are read-only data sources (analogous to REST GET
        endpoints) that LLMs can fetch.
        """
        self._resources[uri] = {
            "uri": uri,
            "name": name,
            "description": description,
            "handler": handler,
        }

    # ── Tool Invocation ────────────────────────────────────────────

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> dict:
        """Execute tool *name* with the supplied *arguments*.

        Returns an MCP-formatted response dict:

        .. code-block:: python

            {
                "content": [{"type": "text", "text": "..."}],
                "isError": False,
            }
        """
        tool = self._tools.get(name)
        if not tool:
            return {
                "content": [{"type": "text", "text": f"Unknown tool: {name}"}],
                "isError": True,
            }

        try:
            handler = tool["handler"]
            if asyncio.iscoroutinefunction(handler):
                result = await handler(**arguments)
            else:
                result = handler(**arguments)
            return {
                "content": [{"type": "text", "text": str(result)}],
                "isError": False,
            }
        except Exception as exc:
            logger.exception(f"MCP tool '{name}' failed")
            return {
                "content": [{"type": "text", "text": str(exc)}],
                "isError": True,
            }

    # ── Introspection ──────────────────────────────────────────────

    def list_tools(self) -> list[dict[str, Any]]:
        """Return metadata for every registered MCP tool.

        Each dict contains ``name``, ``description``, and
        ``inputSchema`` keys, conforming to the MCP tool list format.
        """
        return [
            {
                "name": t["name"],
                "description": t["description"],
                "inputSchema": t["inputSchema"],
            }
            for t in self._tools.values()
        ]

    def list_resources(self) -> list[dict[str, Any]]:
        """Return metadata for every resource URI."""
        return [
            {
                "uri": r["uri"],
                "name": r["name"],
                "description": r["description"],
            }
            for r in self._resources.values()
        ]

    # ── Properties ─────────────────────────────────────────────────

    @property
    def is_running(self) -> bool:
        return self._is_running

    @property
    def tool_count(self) -> int:
        return len(self._tools)


def get_mcp_server() -> MCPServer:
    """Return the application-global :class:`MCPServer` singleton.

    Creates it on first call if it does not already exist.
    """
    global _mcp_server
    if _mcp_server is None:
        _mcp_server = MCPServer()
    return _mcp_server
