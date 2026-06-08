"""Chat processing service."""
from typing import Optional
from uuid import UUID
from backend.services.llm import get_llm_service
from backend.core.logging import get_logger

logger = get_logger(__name__)


class ChatService:
    """Handles chat message processing and LLM interaction."""

    SYSTEM_PROMPT = (
        "You are JARVIS, an advanced AI voice assistant. You are helpful, concise, and knowledgeable. "
        "Respond naturally and conversationally. Keep responses under 200 words unless asked for detail. "
        "If you can't answer something, be honest about it."
    )

    def __init__(self):
        self.llm = get_llm_service()

    async def process_message(
        self,
        message: str,
        conversation_id: Optional[UUID] = None,
        user_id: Optional[UUID] = None,
        temperature: float = 0.3,
        max_tokens: int = 1024,
    ) -> dict:
        """
        Process a user message and return the assistant's response.

        Returns:
            {"reply": str, "conversation_id": UUID, "tokens_used": int}
        """
        # Build messages list with system prompt
        messages = [
            {"role": "system", "content": self.SYSTEM_PROMPT},
        ]

        # TODO: Load recent conversation history from DB
        # For now, just the current message
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
        conversation_id: Optional[UUID] = None,
        user_id: Optional[UUID] = None,
        temperature: float = 0.3,
        max_tokens: int = 1024,
    ):
        """Process a message and stream the response."""
        messages = [
            {"role": "system", "content": self.SYSTEM_PROMPT},
            {"role": "user", "content": message},
        ]

        async for chunk in self.llm.complete_stream(messages, temperature, max_tokens):
            yield chunk


# Global instance
_chat_service: Optional[ChatService] = None


def get_chat_service() -> ChatService:
    global _chat_service
    if _chat_service is None:
        _chat_service = ChatService()
    return _chat_service
