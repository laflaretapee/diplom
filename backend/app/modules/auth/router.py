"""Auth endpoints: login, refresh, logout, me."""
from __future__ import annotations

import secrets

from fastapi import APIRouter, Cookie, Depends, Header, HTTPException, Response, status
from jose import JWTError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.config import get_settings
from backend.app.core.deps import get_current_user
from backend.app.core.rate_limit import RateLimitPolicy, rate_limit
from backend.app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_refresh_token,
)
from backend.app.db.session import get_db_session
from backend.app.models.user import User
from backend.app.modules.auth.schemas import LoginRequest, LoginResponse, TokenResponse, UserInfo
from backend.app.modules.auth.service import authenticate_user, build_login_response

router = APIRouter(prefix="/auth", tags=["auth"])

REFRESH_COOKIE = "refresh_token"
CSRF_COOKIE = "csrf_token"
CSRF_HEADER = "X-CSRF-Token"
COOKIE_MAX_AGE = 30 * 24 * 60 * 60  # 30 days in seconds
REFRESH_COOKIE_PATH = "/api/v1/auth"
CSRF_COOKIE_PATH = "/"


def _new_csrf_token() -> str:
    return secrets.token_urlsafe(32)


def _set_refresh_cookie(response: Response, token: str) -> None:
    settings = get_settings()
    response.set_cookie(
        key=REFRESH_COOKIE,
        value=token,
        httponly=True,
        secure=settings.cookie_secure,
        samesite=settings.cookie_samesite,
        max_age=COOKIE_MAX_AGE,
        path=REFRESH_COOKIE_PATH,
    )


def _set_csrf_cookie(response: Response, token: str) -> None:
    settings = get_settings()
    response.set_cookie(
        key=CSRF_COOKIE,
        value=token,
        httponly=False,
        secure=settings.cookie_secure,
        samesite=settings.cookie_samesite,
        max_age=COOKIE_MAX_AGE,
        path=CSRF_COOKIE_PATH,
    )


def _clear_auth_cookies(response: Response) -> None:
    settings = get_settings()
    response.delete_cookie(
        key=REFRESH_COOKIE,
        path=REFRESH_COOKIE_PATH,
        secure=settings.cookie_secure,
        samesite=settings.cookie_samesite,
    )
    response.delete_cookie(
        key=CSRF_COOKIE,
        path=CSRF_COOKIE_PATH,
        secure=settings.cookie_secure,
        samesite=settings.cookie_samesite,
    )
    # Cleanup legacy path used before SPA auth bootstrap was introduced.
    response.delete_cookie(
        key=CSRF_COOKIE,
        path=REFRESH_COOKIE_PATH,
        secure=settings.cookie_secure,
        samesite=settings.cookie_samesite,
    )


def _verify_csrf(
    csrf_cookie: str | None,
    csrf_header: str | None,
) -> None:
    if not csrf_cookie or not csrf_header:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="CSRF validation failed",
        )
    if not secrets.compare_digest(csrf_cookie, csrf_header):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="CSRF validation failed",
        )


@router.post("/login", response_model=LoginResponse)
async def login(
    body: LoginRequest,
    response: Response,
    _: None = rate_limit(
        RateLimitPolicy(
            bucket="auth-login",
            limit=get_settings().auth_rate_limit_requests,
            window_seconds=get_settings().auth_rate_limit_window_seconds,
        )
    ),
    db: AsyncSession = Depends(get_db_session),
) -> LoginResponse:
    user = await authenticate_user(body.email, body.password, db)
    login_resp, refresh_token = build_login_response(user)
    _set_refresh_cookie(response, refresh_token)
    _set_csrf_cookie(response, _new_csrf_token())
    return login_resp


@router.post("/refresh", response_model=TokenResponse)
async def refresh(
    response: Response,
    refresh_token: str | None = Cookie(default=None, alias=REFRESH_COOKIE),
    csrf_cookie: str | None = Cookie(default=None, alias=CSRF_COOKIE),
    csrf_header: str | None = Header(default=None, alias=CSRF_HEADER),
    _: None = rate_limit(
        RateLimitPolicy(
            bucket="auth-refresh",
            limit=get_settings().refresh_rate_limit_requests,
            window_seconds=get_settings().refresh_rate_limit_window_seconds,
        )
    ),
    db: AsyncSession = Depends(get_db_session),
) -> TokenResponse:
    credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired refresh token",
    )
    if not refresh_token:
        raise credentials_error
    _verify_csrf(csrf_cookie, csrf_header)
    try:
        payload = decode_refresh_token(refresh_token)
    except JWTError:
        raise credentials_error

    user_id: str = payload["sub"]
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None or not user.is_active:
        raise credentials_error

    new_access = create_access_token(str(user.id), user.role.value)
    new_refresh = create_refresh_token(str(user.id))
    _set_refresh_cookie(response, new_refresh)
    _set_csrf_cookie(response, _new_csrf_token())
    return TokenResponse(access_token=new_access)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    response: Response,
    csrf_cookie: str | None = Cookie(default=None, alias=CSRF_COOKIE),
    csrf_header: str | None = Header(default=None, alias=CSRF_HEADER),
) -> None:
    _verify_csrf(csrf_cookie, csrf_header)
    _clear_auth_cookies(response)


@router.get("/me", response_model=UserInfo)
async def me(user: User = Depends(get_current_user)) -> UserInfo:
    """Return current authenticated user info."""
    return UserInfo(
        id=str(user.id),
        email=user.email,
        name=user.name,
        role=user.role.value,
        is_active=user.is_active,
    )
