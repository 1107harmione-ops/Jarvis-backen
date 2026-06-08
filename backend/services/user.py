"""User profile management service."""
from typing import Optional
from uuid import UUID
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from backend.models.user import User
from backend.core.security import hash_password, generate_api_key
from backend.core.logging import get_logger

logger = get_logger(__name__)


class UserService:
    """Manage user profiles and settings."""

    @staticmethod
    async def get_user(db: AsyncSession, user_id: UUID) -> Optional[dict]:
        result = await db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if not user:
            return None
        return {
            "id": str(user.id),
            "username": user.username,
            "email": user.email,
            "role": user.role,
            "is_active": user.is_active,
            "is_verified": user.is_verified,
            "preferences": user.preferences or {},
            "created_at": user.created_at.isoformat() if user.created_at else None,
        }

    @staticmethod
    async def update_user(db: AsyncSession, user_id: UUID, updates: dict) -> dict:
        result = await db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if not user:
            raise ValueError("User not found")

        if "username" in updates:
            user.username = updates["username"]
        if "email" in updates:
            user.email = updates["email"]
        if "password" in updates:
            user.hashed_password = hash_password(updates["password"])
        if "preferences" in updates:
            user.preferences = updates["preferences"]

        await db.flush()
        return await UserService.get_user(db, user_id)

    @staticmethod
    async def delete_user(db: AsyncSession, user_id: UUID) -> bool:
        result = await db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if not user:
            return False
        await db.delete(user)
        return True

    @staticmethod
    async def generate_api_key(db: AsyncSession, user_id: UUID) -> dict:
        result = await db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if not user:
            raise ValueError("User not found")

        raw_key, key_hash = generate_api_key()
        user.api_key_hash = key_hash
        await db.flush()

        return {"api_key": raw_key, "note": "Save this key — it will not be shown again"}


# Global instance
_user_service: Optional[UserService] = None


def get_user_service() -> UserService:
    global _user_service
    if _user_service is None:
        _user_service = UserService()
    return _user_service
