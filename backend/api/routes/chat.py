"""Chat routes — send messages, stream responses, manage conversation history."""

from __future__ import annotations

import json
from typing import AsyncGenerator, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.api.dependencies.auth import get_current_user
from backend.api.dependencies.database import get_db
from backend.models.conversation import Conversation
from backend.models.message import Message
from backend.models.user import User
from backend.schemas.chat import ChatRequest, ChatResponse, StreamChunk
from backend.schemas.conversation import (
    ConversationCreate,
    ConversationListResponse,
    ConversationResponse,
)

router = APIRouter(prefix="/chat", tags=["chat"])


# ── Helper ─────────────────────────────────────────────────────────────


async def _get_user_conversation(
    conversation_id: UUID,
    user_id: UUID,
    db: AsyncSession,
) -> Conversation:
    """Fetch a conversation owned by the user or raise 404."""
    result = await db.execute(
        select(Conversation).where(
            Conversation.id == conversation_id,
            Conversation.user_id == user_id,
        )
    )
    conversation = result.scalar_one_or_none()
    if conversation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found",
        )
    return conversation


def _build_chat_context(messages: list[Message]) -> list[dict]:
    """Convert Message ORM rows to the LLM context format."""
    return [
        {"role": msg.role, "content": msg.content}
        for msg in messages
    ]


# ── Chat Completion ────────────────────────────────────────────────────


@router.post("", response_model=ChatResponse)
async def chat_completion(
    payload: ChatRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ChatResponse:
    """Send a message and receive an LLM-generated reply.

    If ``conversation_id`` is provided the message is appended to that
    conversation; otherwise a new conversation is created.
    """
    # ── Resolve or create conversation ────────────────────────────
    if payload.conversation_id:
        conversation = await _get_user_conversation(
            payload.conversation_id, current_user.id, db
        )
    else:
        conversation = Conversation(
            user_id=current_user.id,
            title=payload.message[:80],
        )
        db.add(conversation)
        await db.flush()

    # ── Save user message ─────────────────────────────────────────
    user_message = Message(
        conversation_id=conversation.id,
        role="user",
        content=payload.message,
        token_count=0,  # TODO: count tokens
    )
    db.add(user_message)

    # ── Generate LLM response (placeholder) ──────────────────────
    # TODO: delegate to LLM service with conversation context
    assistant_content = (
        f"This is a placeholder response. "
        f"You said: '{payload.message[:50]}{'…' if len(payload.message) > 50 else ''}'"
    )
    tokens_used = len(payload.message.split()) + len(assistant_content.split())

    assistant_message = Message(
        conversation_id=conversation.id,
        role="assistant",
        content=assistant_content,
        token_count=tokens_used,
    )
    db.add(assistant_message)
    await db.flush()

    return ChatResponse(
        reply=assistant_content,
        conversation_id=conversation.id,
        message_id=assistant_message.id,
        tokens_used=tokens_used,
    )


# ── Streaming Chat ─────────────────────────────────────────────────────


async def _generate_stream(payload: ChatRequest, user: User, db: AsyncSession) -> AsyncGenerator[str, None]:
    """SSE event stream for real-time LLM responses."""
    # Resolve or create conversation (same as non-streaming)
    if payload.conversation_id:
        conversation = await _get_user_conversation(
            payload.conversation_id, user.id, db
        )
    else:
        conversation = Conversation(
            user_id=user.id,
            title=payload.message[:80],
        )
        db.add(conversation)
        await db.flush()

    # Save user message
    user_msg = Message(
        conversation_id=conversation.id,
        role="user",
        content=payload.message,
    )
    db.add(user_msg)
    await db.flush()

    # TODO: replace with actual streaming from LLM service
    # Simulate streaming tokens for now
    words = (
        f"This is a streamed placeholder response to: '{payload.message[:40]}…'"
    ).split()

    for word in words:
        chunk = StreamChunk(type="text", content=word + " ", done=False)
        yield f"data: {chunk.model_dump_json()}\n\n"
        import asyncio
        await asyncio.sleep(0.05)  # simulate latency

    # Save assistant message
    assistant_msg = Message(
        conversation_id=conversation.id,
        role="assistant",
        content=" ".join(words),
    )
    db.add(assistant_msg)
    await db.flush()

    # Signal completion
    done_chunk = StreamChunk(type="done", content="", done=True)
    yield f"data: {done_chunk.model_dump_json()}\n\n"


@router.post("/stream")
async def chat_stream(
    payload: ChatRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Stream an LLM response as server-sent events (SSE)."""
    from fastapi.responses import StreamingResponse

    return StreamingResponse(
        _generate_stream(payload, current_user, db),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ── History & Conversation Management ──────────────────────────────────


@router.get("/history", response_model=ConversationListResponse)
async def list_conversations(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ConversationListResponse:
    """List the current user's conversations, newest first."""
    result = await db.execute(
        select(Conversation)
        .where(Conversation.user_id == current_user.id)
        .order_by(Conversation.updated_at.desc())
        .offset(skip)
        .limit(limit)
    )
    items = list(result.scalars().all())

    # Get total count
    count_result = await db.execute(
        select(Conversation).where(Conversation.user_id == current_user.id)
    )
    total = len(count_result.scalars().all())

    return ConversationListResponse(
        items=[ConversationResponse.model_validate(c) for c in items],
        total=total,
    )


@router.get("/{conversation_id}", response_model=ConversationResponse)
async def get_conversation(
    conversation_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ConversationResponse:
    """Get a single conversation (without full message history)."""
    conversation = await _get_user_conversation(conversation_id, current_user.id, db)
    return ConversationResponse.model_validate(conversation)


@router.delete("/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_conversation(
    conversation_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete a conversation and all its messages."""
    conversation = await _get_user_conversation(conversation_id, current_user.id, db)
    await db.delete(conversation)
