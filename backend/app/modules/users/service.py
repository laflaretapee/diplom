"""Business logic for user management."""
from __future__ import annotations

import uuid

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.security import hash_password
from backend.app.models.user import User, UserRole
from backend.app.models.user_point import UserPoint
from backend.app.modules.users.schemas import UserCreateRequest, UserUpdateRequest


async def create_user(body: UserCreateRequest, db: AsyncSession) -> User:
    result = await db.execute(select(User).where(User.email == body.email))
    if result.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User with this email already exists",
        )
    user = User(
        email=body.email,
        password_hash=hash_password(body.password),
        name=body.name,
        role=body.role,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def list_users(
    db: AsyncSession,
    role: UserRole | None = None,
    is_active: bool = True,
) -> list[User]:
    query = select(User).where(User.is_active == is_active)
    if role is not None:
        query = query.where(User.role == role)
    result = await db.execute(query)
    return list(result.scalars().all())


async def get_user(user_id: uuid.UUID, db: AsyncSession) -> User:
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user


async def update_user(user_id: uuid.UUID, body: UserUpdateRequest, db: AsyncSession) -> User:
    user = await get_user(user_id, db)
    if body.role is not None:
        user.role = body.role
    if body.is_active is not None:
        user.is_active = body.is_active
    await db.commit()
    await db.refresh(user)
    return user


async def assign_point(user_id: uuid.UUID, point_id: uuid.UUID, db: AsyncSession) -> None:
    # Verify user exists
    await get_user(user_id, db)

    # Check if already assigned
    result = await db.execute(
        select(UserPoint).where(
            UserPoint.user_id == user_id,
            UserPoint.point_id == point_id,
        )
    )
    if result.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User is already assigned to this point",
        )

    db.add(UserPoint(user_id=user_id, point_id=point_id))
    await db.commit()


async def unassign_point(user_id: uuid.UUID, point_id: uuid.UUID, db: AsyncSession) -> None:
    # Verify user exists
    await get_user(user_id, db)

    result = await db.execute(
        select(UserPoint).where(
            UserPoint.user_id == user_id,
            UserPoint.point_id == point_id,
        )
    )
    link = result.scalar_one_or_none()
    if link is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Assignment not found",
        )
    await db.delete(link)
    await db.commit()
