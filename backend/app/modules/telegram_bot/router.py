from __future__ import annotations

from aiogram import Bot, Dispatcher, Router
from aiogram.filters import CommandStart
from aiogram.types import KeyboardButton, Message, ReplyKeyboardMarkup, Update, WebAppInfo
from fastapi import APIRouter, Header, HTTPException

from backend.app.core.config import get_settings

router = APIRouter(prefix="/telegram-bot", tags=["telegram-bot"])


def build_dispatcher() -> Dispatcher:
    settings = get_settings()
    message_router = Router()

    @message_router.message(CommandStart())
    async def start(message: Message) -> None:
        keyboard = ReplyKeyboardMarkup(
            keyboard=[
                [
                    KeyboardButton(
                        text="Открыть меню",
                        web_app=WebAppInfo(url=settings.telegram_mini_app_url),
                    )
                ]
            ],
            resize_keyboard=True,
        )
        await message.answer(
            "Откройте мини-приложение, чтобы выбрать блюда и оформить заказ.",
            reply_markup=keyboard,
        )

    dp = Dispatcher()
    dp.include_router(message_router)
    return dp


@router.post("/webhook")
async def aiogram_webhook(
    update: dict,
    x_telegram_bot_api_secret_token: str | None = Header(default=None),
) -> dict[str, bool]:
    settings = get_settings()
    if x_telegram_bot_api_secret_token != settings.telegram_webhook_secret:
        raise HTTPException(status_code=403, detail="Invalid Telegram webhook secret")
    if not settings.telegram_bot_token:
        raise HTTPException(status_code=503, detail="Telegram bot token is not configured")

    bot = Bot(token=settings.telegram_bot_token)
    dispatcher = build_dispatcher()
    await dispatcher.feed_update(bot, Update.model_validate(update))
    await bot.session.close()
    return {"ok": True}
