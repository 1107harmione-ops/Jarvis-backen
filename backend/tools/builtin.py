"""
Built-in tools for JARVIS.

Every function decorated with ``@registry.register(...)`` is
automatically collected at import time and exposed through the tool
registry, the MCP layer, and the REST API.
"""
from backend.tools import registry
from backend.tools.sandbox import SandboxedExecutor
from backend.core.logging import get_logger
import time

logger = get_logger(__name__)


# ── System Tools ────────────────────────────────────────────────────────


@registry.register(
    name="get_time",
    description="Get the current date and time",
    parameters={
        "type": "object",
        "properties": {},
    },
    category="system",
)
async def get_time():
    """Return the current server datetime and Unix timestamp."""
    return {
        "datetime": time.strftime("%Y-%m-%d %H:%M:%S %Z"),
        "timestamp": time.time(),
    }


@registry.register(
    name="get_system_info",
    description="Get basic system information",
    parameters={"type": "object", "properties": {}},
    category="system",
)
async def get_system_info():
    """Return OS, architecture, and hostname of the server."""
    import platform

    return {
        "os": platform.system(),
        "release": platform.release(),
        "version": platform.version(),
        "architecture": platform.machine(),
        "hostname": platform.node(),
    }


@registry.register(
    name="list_files",
    description="List files in a directory (sandboxed, restricted to data directory)",
    parameters={
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Directory path relative to the configured MCP filesystem root",
            },
        },
        "required": ["path"],
    },
    category="filesystem",
    requires_confirmation=True,
)
async def list_files(path: str = "."):
    """Return a directory listing confined below ``mcp_filesystem_root``.

    Path-traversal attempts that escape the root are rejected.
    """
    import os

    from backend.core.config import get_settings

    root = get_settings().mcp_filesystem_root
    safe_path = os.path.normpath(os.path.join(root, path))

    if not safe_path.startswith(os.path.normpath(root)):
        return {"error": "Path traversal denied"}

    if not os.path.isdir(safe_path):
        return {"error": f"Not a directory: {path}"}

    files = []
    for f in os.listdir(safe_path):
        fp = os.path.join(safe_path, f)
        try:
            size = os.path.getsize(fp)
        except OSError:
            size = 0
        files.append({
            "name": f,
            "type": "dir" if os.path.isdir(fp) else "file",
            "size": size,
        })

    return {"path": path, "files": files}


@registry.register(
    name="run_command",
    description="Run a sandboxed shell command (whitelisted commands only)",
    parameters={
        "type": "object",
        "properties": {
            "command": {
                "type": "string",
                "description": "Shell command to execute",
            },
            "timeout": {
                "type": "integer",
                "description": "Maximum execution time in seconds",
            },
        },
        "required": ["command"],
    },
    category="system",
    requires_confirmation=True,
)
async def run_command(command: str, timeout: int = 10):
    """Execute *command* inside the :class:`SandboxedExecutor` sandbox."""
    result = await SandboxedExecutor.execute(command, timeout=timeout)
    return result


# ── Web Tools ──────────────────────────────────────────────────────────


@registry.register(
    name="search_web",
    description="Search the web (requires web search API)",
    parameters={
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Search query",
            },
        },
        "required": ["query"],
    },
    category="web",
)
async def search_web(query: str):
    """Placeholder — replace with actual web search API integration."""
    return {
        "query": query,
        "results": [],
        "note": "Web search API not configured",
    }


# ── Device Tools ───────────────────────────────────────────────────────


@registry.register(
    name="send_notification",
    description="Send a push notification to the user's device",
    parameters={
        "type": "object",
        "properties": {
            "title": {
                "type": "string",
                "description": "Notification title",
            },
            "body": {
                "type": "string",
                "description": "Notification body",
            },
        },
        "required": ["title", "body"],
    },
    category="device",
    requires_auth=True,
)
async def send_notification(title: str, body: str):
    """Placeholder — integrate with Firebase Cloud Messaging (FCM)."""
    logger.info(f"Notification: [{title}] {body}")
    return {"sent": True, "title": title, "body": body}
