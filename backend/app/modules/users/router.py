"""User management endpoints (super_admin only)."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.deps import require_super_admin
from backend.app.db.session import get_db_session
from backend.app.models.user import User, UserRole
from backend.app.modules.users import service
from backend.app.modules.users.schemas import (
    AssignPointRequest,
    UserCreateRequest,
    UserResponse,
    UserUpdateRequest,
)

router = APIRouter(prefix="/users", tags=["users"])


def _to_response(user: User) -> UserResponse:
    return UserResponse(
        id=str(user.id),
        email=user.email,
        name=user.name,
        role=user.role.value,
        is_active=user.is_active,
        created_at=user.created_at,
    )


@router.post("", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    body: UserCreateRequest,
    _: User = Depends(require_super_admin),
    db: AsyncSession = Depends(get_db_session),
) -> UserResponse:
    user = await service.create_user(body, db)
    return _to_response(user)


@router.get("", response_model=list[UserResponse])
async def list_users(
    role: UserRole | None = None,
    is_active: bool = True,
    _: User = Depends(require_super_admin),
    db: AsyncSession = Depends(get_db_session),
) -> list[UserResponse]:
    users = await service.list_users(db, role=role, is_active=is_active)
    return [_to_response(u) for u in users]


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: uuid.UUID,
    _: User = Depends(require_super_admin),
    db: AsyncSession = Depends(get_db_session),
) -> UserResponse:
    user = await service.get_user(user_id, db)
    return _to_response(user)


@router.patch("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: uuid.UUID,
    body: UserUpdateRequest,
    _: User = Depends(require_super_admin),
    db: AsyncSession = Depends(get_db_session),
) -> UserResponse:
    user = await service.update_user(user_id, body, db)
    return _to_response(user)


@router.post("/{user_id}/points", status_code=status.HTTP_204_NO_CONTENT)
async def assign_point(
    user_id: uuid.UUID,
    body: AssignPointRequest,
    _: User = Depends(require_super_admin),
    db: AsyncSession = Depends(get_db_session),
) -> None:
    await service.assign_point(user_id, body.point_id, db)


@router.delete("/{user_id}/points/{point_id}", status_code=status.HTTP_204_NO_CONTENT)
async def unassign_point(
    user_id: uuid.UUID,
    point_id: uuid.UUID,
    _: User = Depends(require_super_admin),
    db: AsyncSession = Depends(get_db_session),
) -> None:
    await service.unassign_point(user_id, point_id, db)
