from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.config import get_settings
from backend.app.core.deps import get_current_user
from backend.app.core.rate_limit import RateLimitPolicy, rate_limit
from backend.app.db.session import get_db_session
from backend.app.models.user import User
from backend.app.modules.notifications.schemas import (
    NotificationPreferences,
    NotificationPreferencesUpdate,
    NotificationsModuleStatus,
    OperationStatusResponse,
    TelegramLinkResponse,
    TelegramStatusResponse,
    TelegramWebhookUpdate,
)
from backend.app.modules.notifications.service import (
    generate_link_code,
    get_notification_preferences,
    get_status,
    get_telegram_status,
    process_telegram_webhook,
    unlink_telegram,
    update_notification_preferences,
)

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("/status")
async def notifications_status() -> NotificationsModuleStatus:
    return get_status().model_dump()


@router.post("/telegram/link", response_model=TelegramLinkResponse)
async def create_telegram_link(
    _: None = rate_limit(
        RateLimitPolicy(
            bucket="telegram-link",
            limit=get_settings().telegram_link_rate_limit_requests,
            window_seconds=get_settings().telegram_link_rate_limit_window_seconds,
        )
    ),
    user: User = Depends(get_current_user),
) -> TelegramLinkResponse:
    return await generate_link_code(user.id)


@router.get("/preferences", response_model=NotificationPreferences)
async def notification_preferences(
    user: User = Depends(get_current_user),
) -> NotificationPreferences:
    return get_notification_preferences(user)


@router.patch("/preferences", response_model=NotificationPreferences)
async def patch_notification_preferences(
    payload: NotificationPreferencesUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> NotificationPreferences:
    return await update_notification_preferences(user, payload, db)


@router.get("/telegram/status", response_model=TelegramStatusResponse)
async def telegram_status(
    user: User = Depends(get_current_user),
) -> TelegramStatusResponse:
    return get_telegram_status(user)


@router.post("/telegram/unlink", response_model=OperationStatusResponse)
async def telegram_unlink(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> OperationStatusResponse:
    await unlink_telegram(user, db)
    return OperationStatusResponse(ok=True)


@router.post("/telegram/webhook", response_model=OperationStatusResponse)
async def telegram_webhook(
    update: TelegramWebhookUpdate,
    _: None = rate_limit(
        RateLimitPolicy(
            bucket="telegram-webhook",
            limit=get_settings().telegram_webhook_rate_limit_requests,
            window_seconds=get_settings().telegram_webhook_rate_limit_window_seconds,
        )
    ),
    db: AsyncSession = Depends(get_db_session),
    secret: str | None = Header(default=None, alias="X-Telegram-Bot-Api-Secret-Token"),
) -> OperationStatusResponse:
    settings = get_settings()
    if secret != settings.telegram_webhook_secret:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid secret")
    await process_telegram_webhook(update, db)
    return OperationStatusResponse(ok=True)
