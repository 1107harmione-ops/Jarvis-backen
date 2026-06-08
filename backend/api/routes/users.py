"""User management routes — CRUD and API key generation."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.dependencies.auth import get_current_user, require_role
from backend.api.dependencies.database import get_db
from backend.core.security import generate_api_key, hash_password
from backend.models.user import User
from backend.schemas.user import APIKeyResponse, UserResponse, UserUpdate

router = APIRouter(prefix="/users", tags=["users"])


# ── Admin: List All Users ──────────────────────────────────────────────


@router.get("", response_model=list[UserResponse])
async def list_users(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    admin: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
) -> list[UserResponse]:
    """List all users (admin only)."""
    result = await db.execute(
        select(User).order_by(User.created_at.desc()).offset(skip).limit(limit)
    )
    users = result.scalars().all()
    return [UserResponse.model_validate(u) for u in users]


# ── Get User Details ───────────────────────────────────────────────────


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UserResponse:
    """Get a user's public profile.

    Regular users can only view their own profile; admins can view any.
    """
    if current_user.role != "admin" and current_user.id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only view your own profile",
        )

    result = await db.execute(select(User).where(User.id == user_id))
    user: Optional[User] = result.scalar_one_or_none()

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    return UserResponse.model_validate(user)


# ── Update User ────────────────────────────────────────────────────────


@router.put("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: UUID,
    payload: UserUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UserResponse:
    """Update a user's profile.

    Regular users can only update their own profile; admins can update any.
    """
    if current_user.role != "admin" and current_user.id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only update your own profile",
        )

    result = await db.execute(select(User).where(User.id == user_id))
    user: Optional[User] = result.scalar_one_or_none()

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    # Apply allowed updates
    if payload.username is not None:
        # Check uniqueness
        existing = await db.execute(
            select(User).where(User.username == payload.username, User.id != user_id)
        )
        if existing.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Username is already taken",
            )
        user.username = payload.username

    if payload.email is not None:
        existing = await db.execute(
            select(User).where(User.email == payload.email, User.id != user_id)
        )
        if existing.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Email is already in use",
            )
        user.email = payload.email

    if payload.preferences is not None:
        user.preferences = payload.preferences

    user.updated_at = datetime.now(timezone.utc)
    await db.flush()

    return UserResponse.model_validate(user)


# ── Delete User (Admin) ────────────────────────────────────────────────


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: UUID,
    admin: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete a user account (admin only)."""
    result = await db.execute(select(User).where(User.id == user_id))
    user: Optional[User] = result.scalar_one_or_none()

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    await db.delete(user)


# ── Generate API Key ───────────────────────────────────────────────────


@router.post("/api-key", response_model=APIKeyResponse)
async def generate_new_api_key(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> APIKeyResponse:
    """Generate a new API key for the authenticated user.

    The raw key is returned only once; the stored hash is used for
    subsequent verification.
    """
    raw_key, key_hash = generate_api_key()
    current_user.api_key_hash = key_hash

    result = await db.execute(select(User).where(User.id == current_user.id))
    db_user = result.scalar_one_or_none()
    if db_user:
        db_user.api_key_hash = key_hash

    return APIKeyResponse(
        key=raw_key,
        created_at=datetime.now(timezone.utc),
    )
