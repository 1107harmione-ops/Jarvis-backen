"""Conversation management routes — CRUD for conversations."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional
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
from backend.schemas.conversation import (
    ConversationCreate,
    ConversationListResponse,
    ConversationResponse,
)

router = APIRouter(prefix="/conversations", tags=["conversations"])


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


@router.get("", response_model=ConversationListResponse)
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
        .limit(limit + 1)  # fetch one extra to detect if there are more
    )
    rows = list(result.scalars().all())
    has_more = len(rows) > limit
    items = rows[:limit]

    # Total count
    count_result = await db.execute(
        select(Conversation).where(Conversation.user_id == current_user.id)
    )
    total = len(count_result.scalars().all())

    return ConversationListResponse(
        items=[ConversationResponse.model_validate(c) for c in items],
        total=total,
    )


@router.post("", response_model=ConversationResponse, status_code=status.HTTP_201_CREATED)
async def create_conversation(
    payload: ConversationCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ConversationResponse:
    """Create a new conversation."""
    conversation = Conversation(
        user_id=current_user.id,
        title=payload.title or "New Conversation",
    )
    db.add(conversation)
    await db.flush()
    await db.refresh(conversation)

    return ConversationResponse.model_validate(conversation)


@router.get("/{conversation_id}", response_model=ConversationResponse)
async def get_conversation(
    conversation_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ConversationResponse:
    """Get a conversation with its messages."""
    result = await db.execute(
        select(Conversation)
        .where(
            Conversation.id == conversation_id,
            Conversation.user_id == current_user.id,
        )
        .options(selectinload(Conversation.messages))
    )
    conversation: Optional[Conversation] = result.scalar_one_or_none()

    if conversation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found",
        )

    return ConversationResponse.model_validate(conversation)


@router.put("/{conversation_id}", response_model=ConversationResponse)
async def update_conversation(
    conversation_id: UUID,
    payload: ConversationCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ConversationResponse:
    """Update a conversation's title or context."""
    conversation = await _get_user_conversation(conversation_id, current_user.id, db)

    if payload.title is not None:
        conversation.title = payload.title

    conversation.updated_at = datetime.now(timezone.utc)
    await db.flush()
    await db.refresh(conversation)

    return ConversationResponse.model_validate(conversation)


@router.delete("/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_conversation(
    conversation_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete a conversation and cascade its messages."""
    conversation = await _get_user_conversation(conversation_id, current_user.id, db)
    await db.delete(conversation)
