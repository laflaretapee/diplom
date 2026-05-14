from __future__ import annotations

import logging

import httpx
from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.types import Update
from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response
from fastapi.responses import JSONResponse
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

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/sales-telegram", tags=["sales-telegram"])

# ── Bot / Dispatcher singletons ───────────────────────────────────────────────

_dp = Dispatcher()
_bot: Bot | None = None


def get_bot() -> Bot:
    global _bot
    if _bot is None:
        settings = get_settings()
        _bot = Bot(
            token=settings.sales_telegram_bot_token,
            default=DefaultBotProperties(parse_mode=ParseMode.HTML),
        )
    return _bot


# ── Webhook reply builders (no outbound connection needed) ────────────────────
# Telegram processes the bot method returned in the HTTP response body —
# this avoids any outbound API calls from the container to api.telegram.org.

def _send(chat_id: int | str, text: str, reply_markup: dict | None = None) -> dict:
    payload: dict = {"method": "sendMessage", "chat_id": chat_id, "text": text}
    if reply_markup is not None:
        payload["reply_markup"] = reply_markup
    return payload


def _mini_app_keyboard(telegram_id: str) -> dict:
    settings = get_settings()
    sep = "&" if "?" in settings.sales_telegram_mini_app_url else "?"
    url = f"{settings.sales_telegram_mini_app_url}{sep}telegram_id={telegram_id}"
    return {
        "inline_keyboard": [[
            {"text": "Открыть меню", "web_app": {"url": url}}
        ]]
    }


def _phone_keyboard() -> dict:
    return {
        "keyboard": [[{"text": "Отправить номер", "request_contact": True}]],
        "resize_keyboard": True,
        "one_time_keyboard": True,
    }


def _location_keyboard() -> dict:
    return {
        "keyboard": [[{"text": "Отправить геолокацию", "request_location": True}]],
        "resize_keyboard": True,
        "one_time_keyboard": True,
    }


def _remove_keyboard() -> dict:
    return {"remove_keyboard": True}


def _reply_markup_for_step(step: RegistrationStep) -> dict | None:
    if step == RegistrationStep.PHONE:
        return _phone_keyboard()
    if step == RegistrationStep.ADDRESS:
        return _location_keyboard()
    if step == RegistrationStep.ADDRESS_DETAILS:
        return _remove_keyboard()
    return None


def _prompt(step: RegistrationStep) -> str:
    if step == RegistrationStep.NAME:
        return "Как вас зовут?"
    if step == RegistrationStep.PHONE:
        return "Укажите номер телефона для связи или нажмите кнопку ниже."
    if step == RegistrationStep.ADDRESS:
        return "Напишите адрес доставки или отправьте геолокацию кнопкой ниже."
    return "Добавьте уточнение к адресу: квартира, подъезд, этаж, домофон или комментарий."


def _fallback_name(user) -> str:
    parts = [str(user.first_name or "").strip(), str(user.last_name or "").strip()]
    full = " ".join(p for p in parts if p)
    return full or str(user.username or "").strip() or "Клиент Telegram"


# ── Geocoding ─────────────────────────────────────────────────────────────────

async def _reverse_geocode(lat: float, lon: float) -> str | None:
    try:
        async with httpx.AsyncClient(timeout=4.0) as client:
            r = await client.get(
                "https://nominatim.openstreetmap.org/reverse",
                params={
                    "format": "jsonv2",
                    "lat": lat,
                    "lon": lon,
                    "accept-language": "ru",
                    "zoom": 18,
                },
                headers={"User-Agent": "jsancrm-sales-bot/1.0"},
            )
            r.raise_for_status()
            data = r.json()
    except Exception:
        return None
    address = data.get("display_name")
    return str(address).strip() if address else None


# ── Handlers ──────────────────────────────────────────────────────────────────
# Each handler appends one reply dict to `_reply` list.
# The endpoint returns reply[0] as the webhook HTTP response body.

@_dp.message(Command("start"))
async def handle_start(message, db: AsyncSession, _reply: list) -> None:
    if message.from_user is None:
        return
    customer = await get_or_create_sales_customer(
        db,
        telegram_id=str(message.from_user.id),
        fallback_name=_fallback_name(message.from_user),
    )
    set_registration_step(customer, RegistrationStep.NAME)
    await db.commit()
    _reply.append(_send(
        message.chat.id,
        "Перед заказом сохраним данные для доставки. " + _prompt(RegistrationStep.NAME),
    ))


@_dp.message(F.contact)
async def handle_contact(message, db: AsyncSession, _reply: list) -> None:
    if message.from_user is None:
        return
    customer = await get_or_create_sales_customer(
        db,
        telegram_id=str(message.from_user.id),
        fallback_name=_fallback_name(message.from_user),
    )
    step = get_registration_step(customer) or RegistrationStep.NAME
    if step != RegistrationStep.PHONE:
        _reply.append(_send(message.chat.id, _prompt(step), _reply_markup_for_step(step)))
        return
    phone = str(message.contact.phone_number or "").strip()
    next_step = apply_registration_step(customer, step, phone)
    set_registration_step(customer, next_step)
    await db.commit()
    if next_step is not None:
        _reply.append(_send(message.chat.id, _prompt(next_step), _reply_markup_for_step(next_step)))
    else:
        _reply.append(_send(
            message.chat.id,
            "Данные сохранены. Теперь можно открыть меню и оформить заказ.",
            _mini_app_keyboard(str(message.from_user.id)),
        ))


@_dp.message(F.location)
async def handle_location(message, db: AsyncSession, _reply: list) -> None:
    if message.from_user is None:
        return
    customer = await get_or_create_sales_customer(
        db,
        telegram_id=str(message.from_user.id),
        fallback_name=_fallback_name(message.from_user),
    )
    step = get_registration_step(customer) or RegistrationStep.NAME
    if step != RegistrationStep.ADDRESS:
        _reply.append(_send(message.chat.id, _prompt(step), _reply_markup_for_step(step)))
        return
    lat = message.location.latitude
    lon = message.location.longitude
    address = await _reverse_geocode(lat, lon) or f"Координаты: {lat}, {lon}"
    next_step = apply_registration_step(customer, step, address)
    set_registration_step(customer, next_step)
    await db.commit()
    if next_step is not None:
        _reply.append(_send(message.chat.id, _prompt(next_step), _reply_markup_for_step(next_step)))
    else:
        _reply.append(_send(
            message.chat.id,
            "Данные сохранены. Теперь можно открыть меню и оформить заказ.",
            _mini_app_keyboard(str(message.from_user.id)),
        ))


@_dp.message(F.text & ~F.text.startswith("/"))
async def handle_text(message, db: AsyncSession, _reply: list) -> None:
    if message.from_user is None:
        return
    customer = await get_or_create_sales_customer(
        db,
        telegram_id=str(message.from_user.id),
        fallback_name=_fallback_name(message.from_user),
    )
    step = get_registration_step(customer) or RegistrationStep.NAME
    text = str(message.text or "").strip()
    if not text:
        _reply.append(_send(message.chat.id, _prompt(step), _reply_markup_for_step(step)))
        return
    next_step = apply_registration_step(customer, step, text)
    set_registration_step(customer, next_step)
    await db.commit()
    if next_step is not None:
        _reply.append(_send(message.chat.id, _prompt(next_step), _reply_markup_for_step(next_step)))
    else:
        _reply.append(_send(
            message.chat.id,
            "Данные сохранены. Теперь можно открыть меню и оформить заказ.",
            _mini_app_keyboard(str(message.from_user.id)),
        ))


# ── Webhook setup (called on app startup) ────────────────────────────────────

async def setup_webhook() -> None:
    settings = get_settings()
    if not settings.sales_telegram_bot_token:
        logger.warning("Sales Telegram bot token not configured, skipping webhook setup")
        return
    if not settings.sales_telegram_webhook_url:
        logger.warning("SALES_TELEGRAM_WEBHOOK_URL not set, skipping webhook setup")
        return
    bot = get_bot()
    await bot.delete_webhook(drop_pending_updates=True)
    await bot.set_webhook(
        url=settings.sales_telegram_webhook_url,
        secret_token=settings.sales_telegram_webhook_secret,
    )
    logger.info(
        "Sales bot webhook set: %s (pending updates dropped)",
        settings.sales_telegram_webhook_url,
    )


# ── FastAPI endpoint ──────────────────────────────────────────────────────────

@router.post("/webhook")
async def aiogram_webhook(
    request: Request,
    x_telegram_bot_api_secret_token: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db_session),
) -> Response:
    settings = get_settings()
    if x_telegram_bot_api_secret_token != settings.sales_telegram_webhook_secret:
        raise HTTPException(status_code=403, detail="Invalid Telegram webhook secret")
    if not settings.sales_telegram_bot_token:
        raise HTTPException(status_code=503, detail="Sales Telegram bot token is not configured")
    update_data = await request.json()
    update = Update(**update_data)
    reply: list[dict] = []
    await _dp.feed_update(get_bot(), update, db=db, _reply=reply)
    if reply:
        return JSONResponse(reply[0])
    return Response()
