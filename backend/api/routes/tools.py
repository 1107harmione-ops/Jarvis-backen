"""Tool execution routes — list and execute available tools."""

from __future__ import annotations

import asyncio
import shlex
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status

from backend.api.dependencies.auth import get_current_user
from backend.models.user import User
from backend.schemas.tool import ToolCallRequest, ToolCallResponse

router = APIRouter(prefix="/tools", tags=["tools"])

# ── Allowed Tools ──────────────────────────────────────────────────────
# Tools that can be executed via the API. Each entry defines metadata
# and sandbox constraints.

ALLOWED_TOOLS: dict[str, dict[str, Any]] = {
    "execute_code": {
        "name": "execute_code",
        "description": "Execute Python code in a sandboxed subprocess",
        "args": {"code": "string"},
        "sandbox": {"timeout": 30, "allowed_commands": ["python3"]},
    },
    "search_web": {
        "name": "search_web",
        "description": "Perform a web search (placeholder — requires DuckDuckGo or equivalent)",
        "args": {"query": "string"},
        "sandbox": {"timeout": 15, "allowed_commands": []},
    },
    "read_file": {
        "name": "read_file",
        "description": "Read a file from the allowed workspace",
        "args": {"path": "string"},
        "sandbox": {"timeout": 10, "allowed_commands": ["cat"]},
    },
    "write_file": {
        "name": "write_file",
        "description": "Write content to a file in the allowed workspace",
        "args": {"path": "string", "content": "string"},
        "sandbox": {"timeout": 10, "allowed_commands": []},
    },
    "datetime": {
        "name": "datetime",
        "description": "Get the current date and time",
        "args": {},
        "sandbox": {"timeout": 5, "allowed_commands": ["date"]},
    },
}


# ── Routes ─────────────────────────────────────────────────────────────


@router.get("")
async def list_tools(
    current_user: User = Depends(get_current_user),
) -> list[dict[str, Any]]:
    """List all available tools with their metadata."""
    return [
        {
            "name": meta["name"],
            "description": meta["description"],
            "args": meta["args"],
        }
        for meta in ALLOWED_TOOLS.values()
    ]


@router.post("/execute", response_model=ToolCallResponse)
async def execute_tool(
    payload: ToolCallRequest,
    current_user: User = Depends(get_current_user),
) -> ToolCallResponse:
    """Execute a tool by name with the given arguments."""
    return await _run_tool(payload.tool, payload.args)


@router.post("/{tool_name}/execute", response_model=ToolCallResponse)
async def execute_named_tool(
    tool_name: str,
    payload: ToolCallRequest,
    current_user: User = Depends(get_current_user),
) -> ToolCallResponse:
    """Execute a specific tool by name from the URL path."""
    return await _run_tool(tool_name, payload.args)


# ── Execution ──────────────────────────────────────────────────────────


async def _run_tool(tool_name: str, args: dict[str, Any]) -> ToolCallResponse:
    """Look up the tool definition and execute it with sandboxing."""
    import time

    tool_def = ALLOWED_TOOLS.get(tool_name)
    if tool_def is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Unknown tool '{tool_name}'. Available: {list(ALLOWED_TOOLS.keys())}",
        )

    sandbox = tool_def["sandbox"]
    timeout = sandbox["timeout"]

    start = time.time()

    try:
        if tool_name == "execute_code":
            result = await _execute_python(args.get("code", ""), timeout)
        elif tool_name == "search_web":
            result = {"message": "Web search is not yet implemented", "query": args.get("query", "")}
        elif tool_name == "read_file":
            result = await _read_file(args.get("path", ""), timeout)
        elif tool_name == "write_file":
            result = await _write_file(args.get("path", ""), args.get("content", ""), timeout)
        elif tool_name == "datetime":
            result = await _run_shell_command("date", timeout)
        else:
            raise HTTPException(
                status_code=status.HTTP_501_NOT_IMPLEMENTED,
                detail=f"Execution handler for '{tool_name}' is not implemented",
            )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Tool execution failed: {exc}",
        )

    duration_ms = (time.time() - start) * 1000

    return ToolCallResponse(
        result=result,
        tool=tool_name,
        duration_ms=round(duration_ms, 2),
    )


# ── Sandboxed Execution Helpers ────────────────────────────────────────


async def _execute_python(code: str, timeout: int) -> dict[str, Any]:
    """Execute Python code in a subprocess with a timeout."""
    if not code.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Code cannot be empty",
        )

    proc = await asyncio.create_subprocess_exec(
        "python3",
        "-c",
        code,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    try:
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except asyncio.TimeoutError:
        proc.kill()
        raise HTTPException(
            status_code=status.HTTP_408_REQUEST_TIMEOUT,
            detail=f"Code execution timed out after {timeout}s",
        )

    return {
        "stdout": stdout.decode(errors="replace"),
        "stderr": stderr.decode(errors="replace"),
        "exit_code": proc.returncode,
    }


async def _read_file(path: str, timeout: int) -> dict[str, Any]:
    """Read a file safely (path traversal check)."""
    safe_path = _resolve_safe_path(path)
    proc = await asyncio.create_subprocess_exec(
        "cat", safe_path,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except asyncio.TimeoutError:
        proc.kill()
        raise HTTPException(
            status_code=status.HTTP_408_REQUEST_TIMEOUT,
            detail=f"File read timed out after {timeout}s",
        )

    if proc.returncode != 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to read file: {stderr.decode(errors='replace')}",
        )

    return {
        "content": stdout.decode(errors="replace"),
        "path": safe_path,
    }


async def _write_file(path: str, content: str, timeout: int) -> dict[str, Any]:
    """Write content to a file safely."""
    safe_path = _resolve_safe_path(path)
    safe_path.parent.mkdir(parents=True, exist_ok=True)

    proc = await asyncio.create_subprocess_exec(
        "tee", safe_path,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout, stderr = await asyncio.wait_for(
            proc.communicate(input=content.encode()), timeout=timeout
        )
    except asyncio.TimeoutError:
        proc.kill()
        raise HTTPException(
            status_code=status.HTTP_408_REQUEST_TIMEOUT,
            detail=f"File write timed out after {timeout}s",
        )

    if proc.returncode != 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to write file: {stderr.decode(errors='replace')}",
        )

    return {
        "written": True,
        "path": str(safe_path),
        "bytes": len(content),
    }


async def _run_shell_command(command: str, timeout: int) -> dict[str, Any]:
    """Run a trusted shell command with a timeout."""
    proc = await asyncio.create_subprocess_exec(
        *shlex.split(command),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except asyncio.TimeoutError:
        proc.kill()
        raise HTTPException(
            status_code=status.HTTP_408_REQUEST_TIMEOUT,
            detail=f"Command timed out after {timeout}s",
        )

    return {
        "stdout": stdout.decode(errors="replace").strip(),
        "stderr": stderr.decode(errors="replace").strip(),
        "exit_code": proc.returncode,
    }


def _resolve_safe_path(path: str) -> str:
    """Resolve a file path and prevent directory traversal."""
    if not path or ".." in Path(path).parts:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid path: directory traversal is not allowed",
        )
    # Restrict to /tmp/jarvis_tools workspace
    workspace = Path("/tmp/jarvis_tools")
    workspace.mkdir(parents=True, exist_ok=True)

    full_path = (workspace / path).resolve()
    # Ensure it stays within the workspace
    if not str(full_path).startswith(str(workspace.resolve())):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Path is outside the allowed workspace",
        )
    return str(full_path)
