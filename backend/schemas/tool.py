from typing import Any

from pydantic import BaseModel


class ToolCallRequest(BaseModel):
    tool: str
    args: dict


class ToolCallResponse(BaseModel):
    result: Any
    tool: str
    duration_ms: float


class ToolListResponse(BaseModel):
    tools: list[dict]
