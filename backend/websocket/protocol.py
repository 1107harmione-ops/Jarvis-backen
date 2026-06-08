from enum import Enum
from pydantic import BaseModel
from typing import Any, Optional
from uuid import uuid4


class MessageType(str, Enum):
    # Client → Server
    USER_MESSAGE = "user_message"
    PING = "ping"
    TYPING = "typing"
    AUDIO_STREAM = "audio_stream"
    COMMAND = "command"

    # Server → Client
    BOT_REPLY = "bot_reply"
    STREAM_CHUNK = "stream_chunk"
    PONG = "pong"
    ERROR = "error"
    STATUS = "status"
    TYPING_INDICATOR = "typing_indicator"

    # System
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    AUTH_REQUIRED = "auth_required"
    AUTH_SUCCESS = "auth_success"


class WSMessage(BaseModel):
    type: MessageType
    data: dict[str, Any] = {}
    msg_id: str = ""

    def model_post_init(self, __context):
        if not self.msg_id:
            self.msg_id = uuid4().hex[:12]


class WSError(BaseModel):
    code: int
    message: str
