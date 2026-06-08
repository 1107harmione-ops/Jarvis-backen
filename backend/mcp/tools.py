"""Bridge between :class:`~backend.tools.registry.ToolRegistry` and the
:class:`~backend.mcp.server.MCPServer`.

:class:`MCPToolAdapter` synchronises every tool from the central registry
into the MCP server so that LLM hosts see the same set of tools exposed
through the REST API.
"""
from backend.tools import registry
from backend.mcp.server import get_mcp_server
from backend.core.logging import get_logger

logger = get_logger(__name__)


class MCPToolAdapter:
    """Adapt JARVIS tools to the MCP format.

    Usage
    -----
    Call ``MCPToolAdapter.register_all()`` once during application
    startup, **after** all tool modules have been loaded:

    .. code-block:: python

        from backend.tools.loader import load_all_tools
        from backend.mcp.tools import MCPToolAdapter

        load_all_tools()
        MCPToolAdapter.register_all()
    """

    @staticmethod
    def register_all() -> None:
        """Register every tool from :data:`~backend.tools.registry.registry` into the MCP server.

        Each tool's parameter schema is forwarded as the ``inputSchema``
        expected by the MCP protocol.  The handler delegates to the
        async :meth:`~backend.tools.registry.ToolRegistry.execute` method
        and returns the serialised result.
        """
        mcp = get_mcp_server()

        def _make_handler(tool_name: str):
            """Factory to capture *tool_name* by value in the closure."""
            async def _handler(**kw: object) -> dict:
                result = await registry.execute(tool_name, kw)
                return result.to_dict()
            return _handler

        for tool_dict in registry.list_tools():
            name: str = tool_dict["name"]
            handler = _make_handler(name)

            mcp.register_tool(
                name=name,
                description=tool_dict["description"],
                input_schema=tool_dict.get(
                    "parameters",
                    {"type": "object", "properties": {}},
                ),
                handler=handler,
            )

        logger.info(f"Registered {registry.count} tools with MCP")
