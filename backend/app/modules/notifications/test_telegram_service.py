from __future__ import annotations

import uuid
from types import SimpleNamespace

import pytest

from backend.app.modules.notifications import service
from backend.app.modules.notifications.schemas import TelegramWebhookUpdate


class DummyResult:
    def __init__(self, value):
        self._value = value

    def scalar_one_or_none(self):
        return self._value


class DummySession:
    def __init__(self, execute_results: list[object] | None = None):
        self._results = list(execute_results or [])

    async def execute(self, _statement):
        value = self._results.pop(0) if self._results else None
        return DummyResult(value)

    async def commit(self):
        return None


def test_parse_telegram_command_text_normalizes_bot_mentions():
    command = service.parse_telegram_command_text(
        "/stock_add@mockbot 3d2d95f2-6f09-4b11-bef3-9e9554d2b3d8 1.250"
    )

    assert command is not None
    assert command.name == "stock_add"
    assert command.args == ["3d2d95f2-6f09-4b11-bef3-9e9554d2b3d8", "1.250"]


def test_parse_telegram_command_text_accepts_callback_like_payloads():
    command = service.parse_telegram_command_text("orders")

    assert command is not None
    assert command.name == "orders"
    assert command.args == []


@pytest.mark.asyncio
async def test_process_telegram_webhook_requires_link_for_non_link_commands(
    monkeypatch: pytest.MonkeyPatch,
):
    sent_messages: list[tuple[str, str]] = []

    async def fake_send(chat_id: str, text: str) -> bool:
        sent_messages.append((chat_id, text))
        return True

    monkeypatch.setattr(service, "send_telegram_message", fake_send)

    update = TelegramWebhookUpdate.model_validate(
        {
            "message": {
                "text": "/orders",
                "chat": {"id": 123456},
            }
        }
    )

    await service.process_telegram_webhook(update, DummySession())

    assert sent_messages == [
        ("123456", "Сначала привяжите аккаунт: получите код в приложении и отправьте /link <код>."),
    ]


@pytest.mark.asyncio
async def test_process_telegram_webhook_handles_start_for_linked_user(
    monkeypatch: pytest.MonkeyPatch,
):
    sent_messages: list[tuple[str, str, dict | None]] = []
    linked_user = SimpleNamespace(
        id=uuid.uuid4(),
        name="Test User",
        telegram_chat_id="777",
    )

    async def fake_send(
        chat_id: str,
        text: str,
        *,
        reply_markup: dict | None = None,
    ) -> bool:
        sent_messages.append((chat_id, text, reply_markup))
        return True

    monkeypatch.setattr(service, "send_telegram_message", fake_send)

    update = TelegramWebhookUpdate.model_validate(
        {
            "message": {
                "text": "/start",
                "chat": {"id": 777},
            }
        }
    )

    await service.process_telegram_webhook(update, DummySession(execute_results=[linked_user]))

    assert sent_messages
    assert sent_messages[0][0] == "777"
    assert "/orders" in sent_messages[0][1]
    assert sent_messages[0][2] is not None
    keyboard = sent_messages[0][2]["inline_keyboard"]
    assert keyboard[0][0]["callback_data"] == "orders"
    assert keyboard[0][1]["callback_data"] == "tasks"
