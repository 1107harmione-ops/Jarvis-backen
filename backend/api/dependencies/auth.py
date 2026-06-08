"""FastAPI dependencies for JWT authentication and authorization."""

from __future__ import annotations

from typing import Optional

from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.dependencies.database import get_db
from backend.core.security import decode_token
from backend.models.device import Device
from backend.models.user import User

# ── Token Extraction Schemes ──────────────────────────────────────────

oauth2_scheme = HTTPBearer(auto_error=False)
oauth2_scheme_optional = HTTPBearer(auto_error=False)

# Simple role hierarchy for privilege checks.
ROLE_HIERARCHY: dict[str, int] = {
    "user": 0,
    "moderator": 1,
    "developer": 2,
    "admin": 3,
}


# ── Dependencies ──────────────────────────────────────────────────────


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Validate the JWT access token and return the authenticated user.

    Raises ``401`` if the token is missing, invalid, or the user
    does not exist or is deactivated.
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials

    try:
        payload = decode_token(token)
    except (JWTError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id = payload.get("sub")
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
        )

    result = await db.execute(select(User).where(User.id == user_id))
    user: Optional[User] = result.scalar_one_or_none()

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account is deactivated",
        )

    return user


async def get_current_user_optional(
    credentials: HTTPAuthorizationCredentials = Depends(oauth2_scheme_optional),
    db: AsyncSession = Depends(get_db),
) -> Optional[User]:
    """Return the current user or ``None`` if no valid token is provided.

    Never raises — useful for endpoints that behave differently for
    authenticated vs. anonymous users.
    """
    if credentials is None:
        return None

    try:
        return await get_current_user(credentials=credentials, db=db)
    except HTTPException:
        return None


def require_role(required_role: str):
    """Dependency factory that checks the authenticated user's role.

    Usage::

        @router.get("/admin/stats", dependencies=[Depends(require_role("admin"))])

    The role hierarchy is ``user < moderator < developer < admin``.
    """
    required_level = ROLE_HIERARCHY.get(required_role, -1)

    async def _role_checker(current_user: User = Depends(get_current_user)) -> User:
        user_level = ROLE_HIERARCHY.get(current_user.role, 0)
        if user_level < required_level:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires role '{required_role}' or higher (current: '{current_user.role}')",
            )
        return current_user

    return _role_checker


async def get_current_device(
    x_device_id: str = Header(None),
    db: AsyncSession = Depends(get_db),
) -> Optional[Device]:
    """Resolve and return a device by the ``X-Device-ID`` header.

    Returns ``None`` when the header is absent or the device is not found.
    """
    if x_device_id is None:
        return None

    result = await db.execute(
        select(Device).where(
            Device.device_id == x_device_id,
            Device.is_active == True,  # noqa: E712
        )
    )
    return result.scalar_one_or_none()
