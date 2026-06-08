from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, field_validator


class MemoryCreate(BaseModel):
    content: str
    memory_type: str = "episodic"
    importance: str = "medium"

    @field_validator("memory_type")
    @classmethod
    def validate_memory_type(cls, v: str) -> str:
        allowed = {"episodic", "semantic", "procedural"}
        if v.lower() not in allowed:
            raise ValueError(
                f"memory_type must be one of {allowed}, got '{v}'"
            )
        return v.lower()

    @field_validator("importance")
    @classmethod
    def validate_importance(cls, v: str) -> str:
        allowed = {"low", "medium", "high", "critical"}
        if v.lower() not in allowed:
            raise ValueError(
                f"importance must be one of {allowed}, got '{v}'"
            )
        return v.lower()


class MemoryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    content: str
    memory_type: str
    importance: str
    meta_data: dict
    created_at: datetime
    expires_at: Optional[datetime] = None


class MemorySearchResponse(BaseModel):
    items: list[MemoryResponse]
    total: int


class MemoryDeleteResponse(BaseModel):
    deleted: bool
    memory_id: UUID
