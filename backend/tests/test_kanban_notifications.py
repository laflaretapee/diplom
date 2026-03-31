from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from backend.app.celery_app import celery_app
from backend.app.modules.kanban import tasks


@pytest.mark.asyncio
async def test_send_assigned_message_includes_board_and_deadline(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    card = SimpleNamespace(
        title="Запустить promo",
        priority="high",
        deadline=datetime(2026, 4, 2, 9, 30, tzinfo=timezone.utc),
    )
    user = SimpleNamespace(id="u-1", telegram_chat_id="777")
    sent_messages: list[tuple[str, str]] = []

    async def fake_get_card_and_assignee(_card_id: str, _assignee_id: str):
        return card, user, "Маркетинг"

    async def fake_send(chat_id: str, text: str, **_: object) -> bool:
        sent_messages.append((chat_id, text))
        return True

    monkeypatch.setattr(tasks, "_get_card_and_assignee", fake_get_card_and_assignee)
    monkeypatch.setattr(tasks, "notification_enabled", lambda _user, _kind: True)
    monkeypatch.setattr(tasks, "send_telegram_message", fake_send)

    await tasks._send_assigned("card-1", "user-1")

    assert sent_messages == [
        (
            "777",
            "📋 Вам назначена карточка:\n"
            "*Запустить promo*\n"
            "Доска: Маркетинг\n"
            "Приоритет: high\n"
            "Дедлайн: 02.04.2026 09:30",
        )
    ]


@pytest.mark.asyncio
async def test_send_assigned_logs_warning_without_telegram_chat(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    card = SimpleNamespace(title="Карточка", priority="medium", deadline=None)
    user = SimpleNamespace(id="user-2", telegram_chat_id=None)

    async def fake_get_card_and_assignee(_card_id: str, _assignee_id: str):
        return card, user, "Операционный контур"

    async def fail_send(*_args: object, **_kwargs: object) -> bool:
        raise AssertionError("message should not be sent")

    monkeypatch.setattr(tasks, "_get_card_and_assignee", fake_get_card_and_assignee)
    monkeypatch.setattr(tasks, "notification_enabled", lambda _user, _kind: True)
    monkeypatch.setattr(tasks, "send_telegram_message", fail_send)

    with caplog.at_level("WARNING"):
        await tasks._send_assigned("card-2", "user-2")

    assert "no telegram_chat_id" in caplog.text


def test_deadline_set_notification_delegates_to_base_task(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    called: list[str] = []

    def fake_send_deadline_notification(card_id: str) -> None:
        called.append(card_id)

    monkeypatch.setattr(tasks, "send_card_deadline_notification", fake_send_deadline_notification)

    tasks.send_card_deadline_set_notification("card-3")

    assert called == ["card-3"]


def test_celery_schedule_includes_overdue_cards() -> None:
    schedule = celery_app.conf.beat_schedule

    assert schedule["check-overdue-cards"]["task"] == "app.modules.kanban.tasks.check_overdue_cards"
    assert schedule["check-overdue-cards"]["schedule"] == 30 * 60

