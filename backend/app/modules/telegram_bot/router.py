from __future__ import annotations

import time

import httpx
from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.config import get_settings
from backend.app.db.session import get_db_session
from backend.app.modules.telegram_bot.service import (
    RegistrationStep,
    apply_registration_step,
    get_or_create_sales_customer,
    get_registration_step,
    set_registration_step,
)

router = APIRouter(prefix="/sales-telegram", tags=["sales-telegram"])


def build_mini_app_url(telegram_id: str) -> str:
    settings = get_settings()
    separator = "&" if "?" in settings.sales_telegram_mini_app_url else "?"
    return f"{settings.sales_telegram_mini_app_url}{separator}telegram_id={telegram_id}"


def build_mini_app_keyboard(telegram_id: str) -> dict[str, list[list[dict[str, object]]]]:
    return {
        "inline_keyboard": [
            [
                {
                    "text": "Открыть меню",
                    "web_app": {"url": build_mini_app_url(telegram_id)},
                }
            ]
        ]
    }


def build_phone_keyboard() -> dict[str, object]:
    return {
        "keyboard": [[{"text": "Отправить номер", "request_contact": True}]],
        "resize_keyboard": True,
        "one_time_keyboard": True,
    }


def build_location_keyboard() -> dict[str, object]:
    return {
        "keyboard": [[{"text": "Отправить геолокацию", "request_location": True}]],
        "resize_keyboard": True,
        "one_time_keyboard": True,
    }


def build_remove_keyboard() -> dict[str, bool]:
    return {"remove_keyboard": True}


def build_prompt(step: RegistrationStep) -> str:
    if step == RegistrationStep.NAME:
        return "Как вас зовут?"
    if step == RegistrationStep.PHONE:
        return "Укажите номер телефона для связи или нажмите кнопку ниже."
    if step == RegistrationStep.ADDRESS:
        return "Напишите адрес доставки или отправьте геолокацию кнопкой ниже."
    return "Добавьте уточнение к адресу: квартира, подъезд, этаж, домофон или комментарий."


def build_fallback_name(user: dict[str, object]) -> str:
    first_name = str(user.get("first_name") or "").strip()
    last_name = str(user.get("last_name") or "").strip()
    username = str(user.get("username") or "").strip()
    full_name = " ".join(part for part in [first_name, last_name] if part)
    return full_name or username or "Клиент Telegram"


def build_send_message(
    chat_id: int | str,
    text: str,
    *,
    reply_markup: dict[str, object] | None = None,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "method": "sendMessage",
        "chat_id": chat_id,
        "text": text,
    }
    if reply_markup is not None:
        payload["reply_markup"] = reply_markup
    return payload


async def reverse_geocode(latitude: float, longitude: float) -> str | None:
    try:
        async with httpx.AsyncClient(timeout=4.0) as client:
            response = await client.get(
                "https://nominatim.openstreetmap.org/reverse",
                params={
                    "format": "jsonv2",
                    "lat": latitude,
                    "lon": longitude,
                    "accept-language": "ru",
                    "zoom": 18,
                },
                headers={"User-Agent": "jsancrm-sales-bot/1.0"},
            )
            response.raise_for_status()
            data = response.json()
    except Exception:
        return None

    address = data.get("display_name")
    return str(address).strip() if address else None


def reply_markup_for_step(step: RegistrationStep) -> dict[str, object] | None:
    if step == RegistrationStep.PHONE:
        return build_phone_keyboard()
    if step == RegistrationStep.ADDRESS:
        return build_location_keyboard()
    if step == RegistrationStep.ADDRESS_DETAILS:
        return build_remove_keyboard()
    return None


async def handle_sales_message(update: dict, db: AsyncSession) -> dict[str, object]:
    message = update.get("message")
    if not isinstance(message, dict):
        return {"ok": True}

    chat = message.get("chat")
    from_user = message.get("from")
    if not isinstance(chat, dict) or not isinstance(from_user, dict):
        return {"ok": True}

    chat_id = chat.get("id")
    telegram_id = from_user.get("id")
    if chat_id is None or telegram_id is None:
        return {"ok": True}

    # Skip messages sent while the bot was offline (older than 60 seconds)
    msg_date = message.get("date")
    if isinstance(msg_date, int) and time.time() - msg_date > 60:
        return {"ok": True}

    text = str(message.get("text") or "").strip()
    customer = await get_or_create_sales_customer(
        db,
        telegram_id=str(telegram_id),
        fallback_name=build_fallback_name(from_user),
    )

    if text and text.split(maxsplit=1)[0].split("@", maxsplit=1)[0] == "/start":
        set_registration_step(customer, RegistrationStep.NAME)
        await db.commit()
        return build_send_message(
            chat_id,
            "Перед заказом сохраним данные для доставки. " + build_prompt(RegistrationStep.NAME),
        )

    step = get_registration_step(customer) or RegistrationStep.NAME
    contact = message.get("contact") if isinstance(message.get("contact"), dict) else None
    location = message.get("location") if isinstance(message.get("location"), dict) else None

    if contact and step == RegistrationStep.PHONE:
        text = str(contact.get("phone_number") or "").strip()
    elif location and step == RegistrationStep.ADDRESS:
        latitude = location.get("latitude")
        longitude = location.get("longitude")
        if isinstance(latitude, (int, float)) and isinstance(longitude, (int, float)):
            address = await reverse_geocode(float(latitude), float(longitude))
            text = address or f"Координаты: {latitude}, {longitude}"

    if not text:
        set_registration_step(customer, step)
        await db.commit()
        return build_send_message(
            chat_id,
            build_prompt(step),
            reply_markup=reply_markup_for_step(step),
        )

    next_step = apply_registration_step(customer, step, text)
    set_registration_step(customer, next_step)
    await db.commit()

    if next_step is not None:
        return build_send_message(
            chat_id,
            build_prompt(next_step),
            reply_markup=reply_markup_for_step(next_step),
        )

    return build_send_message(
        chat_id,
        "Данные сохранены. Теперь можно открыть меню и оформить заказ.",
        reply_markup=build_mini_app_keyboard(str(telegram_id)),
    )


@router.post("/webhook")
async def aiogram_webhook(
    update: dict,
    x_telegram_bot_api_secret_token: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db_session),
) -> dict[str, object]:
    settings = get_settings()
    if x_telegram_bot_api_secret_token != settings.sales_telegram_webhook_secret:
        raise HTTPException(status_code=403, detail="Invalid Telegram webhook secret")
    if not settings.sales_telegram_bot_token:
        raise HTTPException(status_code=503, detail="Sales Telegram bot token is not configured")

    return await handle_sales_message(update, db)
