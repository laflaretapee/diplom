from __future__ import annotations

import socket

from aiogram import Bot, Dispatcher, Router
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.filters import CommandStart
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message, Update, WebAppInfo
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


def build_mini_app_keyboard() -> InlineKeyboardMarkup:
    settings = get_settings()
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Открыть меню",
                    web_app=WebAppInfo(url=settings.sales_telegram_mini_app_url),
                )
            ]
        ]
    )


def build_prompt(step: RegistrationStep) -> str:
    if step == RegistrationStep.NAME:
        return "Как вас зовут?"
    if step == RegistrationStep.PHONE:
        return "Укажите номер телефона для связи."
    return "Напишите адрес доставки."


def build_fallback_name(message: Message) -> str:
    user = message.from_user
    if user is None:
        return "Клиент Telegram"
    full_name = " ".join(part for part in [user.first_name, user.last_name] if part)
    return full_name or user.username or "Клиент Telegram"


def build_ipv4_bot(token: str) -> Bot:
    session = AiohttpSession()
    session._connector_init["family"] = socket.AF_INET
    return Bot(token=token, session=session)


def build_dispatcher(db: AsyncSession) -> Dispatcher:
    message_router = Router()

    @message_router.message(CommandStart())
    async def start(message: Message) -> None:
        if message.from_user is None:
            await message.answer("Не удалось определить Telegram ID. Напишите /start ещё раз.")
            return
        customer = await get_or_create_sales_customer(
            db,
            telegram_id=str(message.from_user.id),
            fallback_name=build_fallback_name(message),
        )
        set_registration_step(customer, RegistrationStep.NAME)
        await db.commit()
        await message.answer(
            "Перед заказом сохраним данные для доставки. " + build_prompt(RegistrationStep.NAME)
        )

    @message_router.message()
    async def collect_customer_data(message: Message) -> None:
        if message.from_user is None:
            await message.answer("Не удалось определить Telegram ID. Напишите /start ещё раз.")
            return

        text = (message.text or "").strip()
        customer = await get_or_create_sales_customer(
            db,
            telegram_id=str(message.from_user.id),
            fallback_name=build_fallback_name(message),
        )
        step = get_registration_step(customer) or RegistrationStep.NAME

        if not text:
            set_registration_step(customer, step)
            await db.commit()
            await message.answer(build_prompt(step))
            return

        next_step = apply_registration_step(customer, step, text)
        set_registration_step(customer, next_step)
        await db.commit()

        if next_step is not None:
            await message.answer(build_prompt(next_step))
            return

        await message.answer(
            "Данные сохранены. Теперь можно открыть меню и оформить заказ.",
            reply_markup=build_mini_app_keyboard(),
        )

    dp = Dispatcher()
    dp.include_router(message_router)
    return dp


@router.post("/webhook")
async def aiogram_webhook(
    update: dict,
    x_telegram_bot_api_secret_token: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db_session),
) -> dict[str, bool]:
    settings = get_settings()
    if x_telegram_bot_api_secret_token != settings.sales_telegram_webhook_secret:
        raise HTTPException(status_code=403, detail="Invalid Telegram webhook secret")
    if not settings.sales_telegram_bot_token:
        raise HTTPException(status_code=503, detail="Sales Telegram bot token is not configured")

    bot = build_ipv4_bot(settings.sales_telegram_bot_token)
    dispatcher = build_dispatcher(db)
    try:
        await dispatcher.feed_update(bot, Update.model_validate(update))
    finally:
        await bot.session.close()
    return {"ok": True}
