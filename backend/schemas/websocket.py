from typing import Any, Optional

from pydantic import BaseModel


class WSMessage(BaseModel):
    type: str
    data: dict[str, Any]
    msg_id: Optional[str] = None


class WSError(BaseModel):
    code: int
    message: str
