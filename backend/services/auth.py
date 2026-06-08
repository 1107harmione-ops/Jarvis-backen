"""Authentication service — user registration, login, token management."""
from typing import Optional
from uuid import UUID
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from backend.models.user import User
from backend.core.security import hash_password, verify_password, create_access_token, create_refresh_token, verify_token
from backend.core.logging import get_logger

logger = get_logger(__name__)


class AuthService:
    """Handles user authentication and authorization."""

    @staticmethod
    async def register_user(
        db: AsyncSession,
        username: str,
        email: str,
        password: str,
    ) -> dict:
        """Register a new user and return tokens."""
        # Check existing user
        result = await db.execute(
            select(User).where((User.username == username) | (User.email == email))
        )
        if result.scalar_one_or_none():
            raise ValueError("Username or email already exists")

        user = User(
            username=username,
            email=email,
            hashed_password=hash_password(password),
        )
        db.add(user)
        await db.flush()

        access_token = create_access_token(subject=str(user.id), role=user.role)
        refresh_token = create_refresh_token(subject=str(user.id))

        logger.info(f"User registered: {username} ({user.id})")

        return {
            "user_id": str(user.id),
            "username": user.username,
            "email": user.email,
            "role": user.role,
            "access_token": access_token,
            "refresh_token": refresh_token,
        }

    @staticmethod
    async def login_user(
        db: AsyncSession,
        username: str,
        password: str,
    ) -> dict:
        """Authenticate a user and return tokens."""
        result = await db.execute(
            select(User).where(User.username == username)
        )
        user = result.scalar_one_or_none()

        if not user or not verify_password(password, user.hashed_password):
            raise ValueError("Invalid username or password")

        if not user.is_active:
            raise ValueError("Account is deactivated")

        access_token = create_access_token(subject=str(user.id), role=user.role)
        refresh_token = create_refresh_token(subject=str(user.id))

        logger.info(f"User logged in: {username}")

        return {
            "user_id": str(user.id),
            "username": user.username,
            "email": user.email,
            "role": user.role,
            "access_token": access_token,
            "refresh_token": refresh_token,
        }

    @staticmethod
    async def refresh_access_token(refresh_token: str) -> dict:
        """Exchange a refresh token for a new access token."""
        payload = verify_token(refresh_token)
        if not payload or payload.exp is None:
            raise ValueError("Invalid or expired refresh token")

        new_access = create_access_token(subject=payload.sub, role=payload.role)

        return {
            "access_token": new_access,
            "token_type": "bearer",
        }

    @staticmethod
    async def get_user_by_id(db: AsyncSession, user_id: UUID) -> Optional[User]:
        """Fetch a user by ID."""
        result = await db.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()


# Global instance
_auth_service: Optional[AuthService] = None


def get_auth_service() -> AuthService:
    global _auth_service
    if _auth_service is None:
        _auth_service = AuthService()
    return _auth_service
