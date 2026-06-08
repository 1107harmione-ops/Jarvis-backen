from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str
    conversation_id: Optional[UUID] = None
    temperature: float = 0.3
    max_tokens: int = 1024


class ChatResponse(BaseModel):
    reply: str
    conversation_id: UUID
    message_id: UUID
    tokens_used: int


class StreamChunk(BaseModel):
    type: str  # text, tool_call, error, done
    content: str = ""
    done: bool = False
