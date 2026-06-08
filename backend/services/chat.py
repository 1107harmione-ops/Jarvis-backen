from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.conversation import Conversation
from backend.models.message import Message
from backend.services.llm import get_llm_service
from backend.core.logging import get_logger

logger = get_logger(__name__)


class ChatService:
    def __init__(self):
        self.llm = get_llm_service()

    async def process_message(
        self,
        message: str,
        db: AsyncSession,
        conversation_id: Optional[UUID] = None,
        user_id: Optional[UUID] = None,
        temperature: float = 0.3,
        max_tokens: int = 1024,
    ) -> dict:
        messages = [
            {"role": "system", "content": (
                "You are JARVIS, an advanced AI voice assistant. "
                "You are helpful, concise, and knowledgeable. "
                "Respond naturally and conversationally. Keep responses under 200 words unless asked for detail. "
                "If you can't answer something, be honest about it."
            )},
        ]

        # Load conversation history from DB
        if conversation_id and user_id:
            result = await db.execute(
                select(Message)
                .where(
                    Message.conversation_id == conversation_id,
                )
                .order_by(Message.created_at.asc())
                .limit(50)
            )
            history = result.scalars().all()
            for msg in history:
                messages.append({"role": msg.role, "content": msg.content})

        # Append user message
        messages.append({"role": "user", "content": message})

        # Get LLM response
        result = await self.llm.complete(messages, temperature, max_tokens)

        return {
            "reply": result.get("content", ""),
            "conversation_id": conversation_id,
            "tokens_used": result.get("tokens_used", 0),
        }

    async def process_message_stream(
        self,
        message: str,
        db: AsyncSession,
        conversation_id: Optional[UUID] = None,
        user_id: Optional[UUID] = None,
        temperature: float = 0.3,
        max_tokens: int = 1024,
    ):
        messages = [
            {"role": "system", "content": (
                "You are JARVIS, an advanced AI voice assistant. "
                "You are helpful, concise, and knowledgeable. "
                "Respond naturally and conversationally. Keep responses under 200 words unless asked for detail."
            )},
        ]

        if conversation_id and user_id:
            result = await db.execute(
                select(Message)
                .where(Message.conversation_id == conversation_id)
                .order_by(Message.created_at.asc())
                .limit(50)
            )
            for msg in result.scalars().all():
                messages.append({"role": msg.role, "content": msg.content})

        messages.append({"role": "user", "content": message})

        async for chunk in self.llm.complete_stream(messages, temperature, max_tokens):
            yield chunk


_chat_service: Optional[ChatService] = None


def get_chat_service() -> ChatService:
    global _chat_service
    if _chat_service is None:
        _chat_service = ChatService()
    return _chat_service
