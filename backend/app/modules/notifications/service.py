from __future__ import annotations

import logging
import random
import re
import uuid

from fastapi import HTTPException, status
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.config import get_settings
from backend.app.core.telegram import send_telegram_message
from backend.app.models.user import User
from backend.app.modules.notifications.schemas import (
    NotificationPreferences,
    NotificationPreferencesUpdate,
    NotificationsModuleStatus,
    TelegramLinkResponse,
    TelegramStatusResponse,
    TelegramWebhookUpdate,
)

logger = logging.getLogger(__name__)

LINK_CODE_TTL_SECONDS = 300
LINK_CODE_RE = re.compile(r"^/link\s+(\d{6})\s*$")
DEFAULT_NOTIFICATION_PREFERENCES = NotificationPreferences().model_dump()


def get_status() -> NotificationsModuleStatus:
    return NotificationsModuleStatus(module="notifications", status="active")


async def _get_redis() -> Redis:
    settings = get_settings()
    return Redis.from_url(settings.redis_url, decode_responses=True)


async def generate_link_code(user_id: uuid.UUID) -> TelegramLinkResponse:
    redis = await _get_redis()
    try:
        for _ in range(10):
            code = f"{random.randint(0, 999999):06d}"
            key = f"tg_link:{code}"
            if await redis.set(key, str(user_id), ex=LINK_CODE_TTL_SECONDS, nx=True):
                return TelegramLinkResponse(
                    code=code,
                    expires_in=LINK_CODE_TTL_SECONDS,
                    instructions=f"Отправьте боту: /link {code}",
                )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Could not allocate Telegram link code",
        )
    finally:
        await redis.aclose()


def get_telegram_status(user: User) -> TelegramStatusResponse:
    return TelegramStatusResponse(
        linked=bool(user.telegram_chat_id),
        chat_id=user.telegram_chat_id,
    )


def get_notification_preferences(user: User) -> NotificationPreferences:
    raw = user.notification_settings if isinstance(user.notification_settings, dict) else {}
    merged = DEFAULT_NOTIFICATION_PREFERENCES.copy()
    for key, value in raw.items():
        if key in merged:
            merged[key] = bool(value)
    return NotificationPreferences(**merged)


def notification_enabled(user: User, notification_type: str) -> bool:
    preferences = get_notification_preferences(user).model_dump()
    return bool(preferences.get(notification_type, True))


async def update_notification_preferences(
    user: User,
    payload: NotificationPreferencesUpdate,
    db: AsyncSession,
) -> NotificationPreferences:
    preferences = get_notification_preferences(user).model_dump()
    preferences.update(payload.model_dump(exclude_none=True))
    user.notification_settings = preferences
    await db.commit()
    await db.refresh(user)
    return NotificationPreferences(**preferences)


async def unlink_telegram(user: User, db: AsyncSession) -> None:
    user.telegram_chat_id = None
    await db.commit()


async def process_telegram_webhook(
    update: TelegramWebhookUpdate,
    db: AsyncSession,
) -> None:
    message = update.message
    if message is None or not message.text:
        return

    match = LINK_CODE_RE.match(message.text.strip())
    if not match:
        return

    code = match.group(1)
    redis = await _get_redis()
    try:
        user_id = await redis.get(f"tg_link:{code}")
        if user_id is None:
            await send_telegram_message(str(message.chat.id), "Код недействителен или истёк.")
            return
        result = await db.execute(select(User).where(User.id == uuid.UUID(user_id)))
        user = result.scalar_one_or_none()
        if user is None:
            await redis.delete(f"tg_link:{code}")
            return

        user.telegram_chat_id = str(message.chat.id)
        await db.commit()
        await redis.delete(f"tg_link:{code}")
        await send_telegram_message(str(message.chat.id), "Аккаунт успешно привязан!")
        logger.info("Linked telegram chat %s to user %s", message.chat.id, user.id)
    finally:
        await redis.aclose()
