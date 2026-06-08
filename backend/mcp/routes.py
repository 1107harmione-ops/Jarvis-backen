"""FastAPI routes that expose the MCP tool surface via HTTP.

These endpoints are used by external LLM hosts (Claude Desktop, Cursor,
etc.) and by the frontend for tool discovery and invocation.
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.mcp.server import get_mcp_server

router = APIRouter(prefix="/mcp", tags=["mcp"])


# ── Request / Response Models ──────────────────────────────────────────


class MCPCallRequest(BaseModel):
    """Payload for invoking an MCP-exposed tool."""
    name: str
    arguments: dict = {}


class MCPCallResponse(BaseModel):
    """Standard MCP tool response."""
    content: list[dict]
    isError: bool = False


# ── Endpoints ──────────────────────────────────────────────────────────


@router.get("/tools", summary="List all MCP-exposed tools")
async def list_tools():
    """Return metadata for every tool registered with the MCP server.

    Each entry includes ``name``, ``description``, and ``inputSchema``
    so that LLMs can dynamically discover available capabilities.
    """
    mcp = get_mcp_server()
    return {"tools": mcp.list_tools()}


@router.post("/call", summary="Call a tool through MCP")
async def call_tool(request: MCPCallRequest):
    """Invoke the tool identified by ``request.name``.

    The ``request.arguments`` dict is forwarded as keyword arguments to
    the underlying tool function.  Returns an MCP-formatted response
    with a ``content`` list and an ``isError`` flag.
    """
    mcp = get_mcp_server()
    result = await mcp.call_tool(request.name, request.arguments)
    return result


@router.get("/tools/{name}", summary="Get metadata for a single MCP tool")
async def get_tool(name: str):
    """Return the specification for a single tool by *name*."""
    mcp = get_mcp_server()
    tools = mcp.list_tools()
    for tool in tools:
        if tool["name"] == name:
            return {"tool": tool}
    raise HTTPException(status_code=404, detail=f"Tool '{name}' not found")
