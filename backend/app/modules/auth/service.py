"""Auth service: login, refresh token logic."""
from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.security import (
    create_access_token,
    create_refresh_token,
    verify_password,
)
from backend.app.models.user import User
from backend.app.modules.auth.schemas import LoginResponse, UserInfo


async def authenticate_user(email: str, password: str, db: AsyncSession) -> User:
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    if user is None or not verify_password(password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive",
        )
    return user


def build_login_response(user: User) -> tuple[LoginResponse, str]:
    """Return (LoginResponse, refresh_token_string)."""
    access_token = create_access_token(str(user.id), user.role.value)
    refresh_token = create_refresh_token(str(user.id))
    response = LoginResponse(
        access_token=access_token,
        user=UserInfo(
            id=str(user.id),
            email=user.email,
            name=user.name,
            role=user.role.value,
            is_active=user.is_active,
        ),
    )
    return response, refresh_token
