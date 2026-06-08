"""Conversation management service."""
from typing import Optional
from uuid import UUID
from sqlalchemy import select, delete, func
from sqlalchemy.ext.asyncio import AsyncSession
from backend.models.conversation import Conversation
from backend.models.message import Message
from backend.core.logging import get_logger

logger = get_logger(__name__)


class ConversationService:
    """Manage conversations and messages."""

    @staticmethod
    async def create_conversation(
        db: AsyncSession,
        user_id: UUID,
        title: Optional[str] = None,
    ) -> dict:
        conv = Conversation(user_id=user_id, title=title or "New Conversation")
        db.add(conv)
        await db.flush()
        return {"id": str(conv.id), "title": conv.title, "created_at": conv.created_at.isoformat()}

    @staticmethod
    async def get_conversation(db: AsyncSession, conversation_id: UUID, user_id: UUID) -> Optional[dict]:
        result = await db.execute(
            select(Conversation).where(
                Conversation.id == conversation_id,
                Conversation.user_id == user_id,
            )
        )
        conv = result.scalar_one_or_none()
        if not conv:
            return None

        # Get messages
        msg_result = await db.execute(
            select(Message).where(Message.conversation_id == conv.id).order_by(Message.created_at)
        )
        messages = [
            {
                "id": str(m.id),
                "role": m.role,
                "content": m.content,
                "created_at": m.created_at.isoformat() if m.created_at else None,
            }
            for m in msg_result.scalars().all()
        ]

        return {
            "id": str(conv.id),
            "title": conv.title,
            "is_active": conv.is_active,
            "messages": messages,
            "created_at": conv.created_at.isoformat() if conv.created_at else None,
            "updated_at": conv.updated_at.isoformat() if conv.updated_at else None,
        }

    @staticmethod
    async def list_conversations(db: AsyncSession, user_id: UUID, limit: int = 50, offset: int = 0) -> dict:
        result = await db.execute(
            select(Conversation).where(
                Conversation.user_id == user_id,
                Conversation.is_active == True,
            ).order_by(Conversation.updated_at.desc()).offset(offset).limit(limit)
        )
        conversations = result.scalars().all()

        # Get total count
        count_result = await db.execute(
            select(func.count()).where(
                Conversation.user_id == user_id,
                Conversation.is_active == True,
            )
        )
        total = count_result.scalar()

        return {
            "items": [
                {
                    "id": str(c.id),
                    "title": c.title,
                    "message_count": 0,  # TODO: count messages
                    "created_at": c.created_at.isoformat() if c.created_at else None,
                    "updated_at": c.updated_at.isoformat() if c.updated_at else None,
                }
                for c in conversations
            ],
            "total": total,
        }

    @staticmethod
    async def delete_conversation(db: AsyncSession, conversation_id: UUID, user_id: UUID) -> bool:
        result = await db.execute(
            select(Conversation).where(
                Conversation.id == conversation_id,
                Conversation.user_id == user_id,
            )
        )
        conv = result.scalar_one_or_none()
        if not conv:
            return False
        await db.delete(conv)
        return True

    @staticmethod
    async def add_message(
        db: AsyncSession,
        conversation_id: UUID,
        role: str,
        content: str,
        token_count: int = 0,
    ) -> dict:
        msg = Message(
            conversation_id=conversation_id,
            role=role,
            content=content,
            token_count=token_count,
        )
        db.add(msg)
        await db.flush()
        return {
            "id": str(msg.id),
            "role": msg.role,
            "content": msg.content,
            "created_at": msg.created_at.isoformat() if msg.created_at else None,
        }


# Global instance
_conversation_service: Optional[ConversationService] = None


def get_conversation_service() -> ConversationService:
    global _conversation_service
    if _conversation_service is None:
        _conversation_service = ConversationService()
    return _conversation_service
