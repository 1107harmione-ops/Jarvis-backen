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
from backend.services.chat import get_chat_service

router = APIRouter(prefix="/chat", tags=["chat"])


async def _get_user_conversation(
    conversation_id: UUID,
    user_id: UUID,
    db: AsyncSession,
) -> Conversation:
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


@router.post("", response_model=ChatResponse)
async def chat_completion(
    payload: ChatRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ChatResponse:
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

    user_message = Message(
        conversation_id=conversation.id,
        role="user",
        content=payload.message,
    )
    db.add(user_message)
    await db.flush()

    chat_service = get_chat_service()
    result = await chat_service.process_message(
        message=payload.message,
        db=db,
        conversation_id=conversation.id,
        user_id=current_user.id,
        temperature=payload.temperature,
        max_tokens=payload.max_tokens,
    )

    assistant_content = result.get("reply", "")
    tokens_used = result.get("tokens_used", 0)

    assistant_message = Message(
        conversation_id=conversation.id,
        role="assistant",
        content=assistant_content,
        token_count=tokens_used,
    )
    db.add(assistant_message)

    conversation.title = assistant_content[:80]
    await db.flush()

    return ChatResponse(
        reply=assistant_content,
        conversation_id=conversation.id,
        message_id=assistant_message.id,
        tokens_used=tokens_used,
    )


async def _generate_stream(
    payload: ChatRequest,
    user: User,
    db: AsyncSession,
) -> AsyncGenerator[str, None]:
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

    user_msg = Message(
        conversation_id=conversation.id,
        role="user",
        content=payload.message,
    )
    db.add(user_msg)
    await db.flush()

    chat_service = get_chat_service()
    full_content = ""
    async for chunk in chat_service.process_message_stream(
        message=payload.message,
        db=db,
        conversation_id=conversation.id,
        user_id=user.id,
        temperature=payload.temperature,
        max_tokens=payload.max_tokens,
    ):
        full_content += chunk
        stream_chunk = StreamChunk(type="text", content=chunk, done=False)
        yield f"data: {stream_chunk.model_dump_json()}\n\n"

    assistant_msg = Message(
        conversation_id=conversation.id,
        role="assistant",
        content=full_content,
    )
    db.add(assistant_msg)
    await db.flush()

    done_chunk = StreamChunk(type="done", content="", done=True)
    yield f"data: {done_chunk.model_dump_json()}\n\n"


@router.post("/stream")
async def chat_stream(
    payload: ChatRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
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


@router.get("/history", response_model=ConversationListResponse)
async def list_conversations(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ConversationListResponse:
    result = await db.execute(
        select(Conversation)
        .where(Conversation.user_id == current_user.id)
        .order_by(Conversation.updated_at.desc())
        .offset(skip)
        .limit(limit)
    )
    items = list(result.scalars().all())

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
    conversation = await _get_user_conversation(conversation_id, current_user.id, db)
    return ConversationResponse.model_validate(conversation)


@router.delete("/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_conversation(
    conversation_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    conversation = await _get_user_conversation(conversation_id, current_user.id, db)
    await db.delete(conversation)
