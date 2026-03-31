"""FastAPI dependency injection: auth, RBAC, and tenant scoping."""
from __future__ import annotations

import uuid
from collections.abc import Callable

from fastapi import Depends, HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.security import decode_access_token
from backend.app.db.session import get_db_session
from backend.app.models.user import User, UserRole
from backend.app.models.user_point import UserPoint

_bearer = HTTPBearer(auto_error=False)

_UNAUTHORIZED = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Not authenticated",
    headers={"WWW-Authenticate": "Bearer"},
)
_FORBIDDEN = HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Security(_bearer),
    db: AsyncSession = Depends(get_db_session),
) -> User:
    if not credentials:
        raise _UNAUTHORIZED
    try:
        payload = decode_access_token(credentials.credentials)
    except JWTError:
        raise _UNAUTHORIZED

    user_id: str = payload.get("sub", "")
    try:
        uid = uuid.UUID(user_id)
    except ValueError:
        raise _UNAUTHORIZED

    result = await db.execute(select(User).where(User.id == uid))
    user = result.scalar_one_or_none()
    if user is None or not user.is_active:
        raise _UNAUTHORIZED
    return user


def require_roles(*roles: UserRole) -> Callable:
    """Dependency factory: ensures current user has one of the given roles."""

    async def _check(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles:
            raise _FORBIDDEN
        return user

    return _check


# Convenience shorthands
require_super_admin = require_roles(UserRole.SUPER_ADMIN)
require_franchisee_or_above = require_roles(UserRole.SUPER_ADMIN, UserRole.FRANCHISEE)
require_manager_or_above = require_roles(
    UserRole.SUPER_ADMIN, UserRole.FRANCHISEE, UserRole.POINT_MANAGER
)
require_any_role = require_roles(
    UserRole.SUPER_ADMIN,
    UserRole.FRANCHISEE,
    UserRole.POINT_MANAGER,
    UserRole.STAFF,
)


async def verify_point_access(
    point_id: uuid.UUID,
    user: User,
    db: AsyncSession,
) -> None:
    """
    Raise HTTP 403 if user does not have access to point_id.
    super_admin always passes.
    """
    if user.role == UserRole.SUPER_ADMIN:
        return
    result = await db.execute(
        select(UserPoint).where(
            UserPoint.user_id == user.id,
            UserPoint.point_id == point_id,
        )
    )
    if result.scalar_one_or_none() is None:
        raise _FORBIDDEN


def require_point_access(point_id_param: str = "point_id") -> Callable:
    """
    Dependency factory: ensures current user is linked to the point
    identified by the path/query parameter named `point_id_param`.
    Usage:
        @router.get("/{point_id}/orders")
        async def list_orders(
            point_id: uuid.UUID,
            _: None = Depends(require_point_access("point_id")),
            user: User = Depends(get_current_user),
            db: AsyncSession = Depends(get_db_session),
        ): ...
    """
    import inspect

    async def _check(
        user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db_session),
        **kwargs: uuid.UUID,
    ) -> None:
        pid = kwargs.get(point_id_param)
        if pid is None:
            raise _FORBIDDEN
        await verify_point_access(pid, user, db)

    # Inject the point_id parameter dynamically so FastAPI resolves it
    sig = inspect.signature(_check)
    params = list(sig.parameters.values())
    point_param = inspect.Parameter(
        point_id_param,
        inspect.Parameter.POSITIONAL_OR_KEYWORD,
        annotation=uuid.UUID,
    )
    new_params = [point_param] + [p for p in params if p.name != "kwargs"]
    _check.__signature__ = sig.replace(parameters=new_params)  # type: ignore[attr-defined]

    return _check
