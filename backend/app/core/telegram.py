from __future__ import annotations

import httpx

from backend.app.core.config import get_settings


async def send_telegram_message(
    chat_id: str,
    text: str,
    *,
    reply_markup: dict | None = None,
) -> bool:
    settings = get_settings()
    if not settings.telegram_bot_token:
        return False

    payload: dict[str, object] = {"chat_id": chat_id, "text": text}
    if reply_markup is not None:
        payload["reply_markup"] = reply_markup

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage",
                json=payload,
                timeout=5.0,
            )
        return response.status_code == 200
    except Exception:
        return False
