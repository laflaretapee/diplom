"""
Notification service для Kanban задач.
Все уведомления идут через этот модуль — он проверяет дубли через notification_log.
"""
from __future__ import annotations

import json
import logging

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.config import get_settings
from backend.app.models.user import User
from backend.app.modules.kanban.models import Card, NotificationLog

logger = logging.getLogger(__name__)

_settings = get_settings()


async def _get_user(db: AsyncSession, user_id: object) -> User | None:
    result = await db.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()


async def _already_sent(
    db: AsyncSession, card_id: object, user_id: object, event_type: str
) -> bool:
    """Проверяем, было ли уже отправлено это уведомление (защита от дублей)."""
    result = await db.execute(
        select(NotificationLog).where(
            NotificationLog.card_id == card_id,
            NotificationLog.user_id == user_id,
            NotificationLog.event_type == event_type,
        )
    )
    return result.scalar_one_or_none() is not None


async def _log_notification(
    db: AsyncSession,
    *,
    card_id: object,
    user_id: object,
    event_type: str,
    status: str = "sent",
    payload: dict | None = None,
) -> None:
    log = NotificationLog(
        card_id=card_id,
        user_id=user_id,
        event_type=event_type,
        status=status,
        payload=payload,
    )
    db.add(log)
    await db.flush()


async def _send_telegram(
    chat_id: str, text: str, reply_markup: dict | None = None
) -> bool:
    """Отправить сообщение в Telegram."""
    token = _settings.telegram_bot_token
    if not token or not chat_id:
        logger.warning("Telegram not configured or no chat_id")
        return False

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload: dict = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
    if reply_markup:
        payload["reply_markup"] = json.dumps(reply_markup)

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
            return True
    except Exception as exc:
        logger.error("Telegram send error: %s", exc)
        return False


def _task_buttons(
    card_id: str,
    assignee_actions: bool = True,
    reviewer_actions: bool = False,
) -> dict:
    """Inline keyboard кнопки для задачи."""
    rows: list[list[dict]] = []
    if assignee_actions:
        rows.append([
            {"text": "✅ Принять", "callback_data": f"task_accept:{card_id}"},
            {"text": "🚀 В работу", "callback_data": f"task_start:{card_id}"},
        ])
        rows.append([
            {"text": "🏁 Завершить", "callback_data": f"task_complete:{card_id}"},
        ])
    if reviewer_actions:
        rows.append([
            {"text": "✔️ Принять результат", "callback_data": f"task_approve:{card_id}"},
            {"text": "🔄 Вернуть в работу", "callback_data": f"task_return:{card_id}"},
        ])
    rows.append([
        {"text": "🔗 Открыть в CRM", "url": f"https://crm.japonica.ru/kanban/card/{card_id}"},
    ])
    return {"inline_keyboard": rows}


async def notify_task_created(db: AsyncSession, card: Card) -> None:
    """Уведомление исполнителю при создании задачи."""
    if not card.assignee_id:
        return
    assignee = await _get_user(db, card.assignee_id)
    creator = await _get_user(db, card.creator_id) if card.creator_id else None
    if not assignee or not assignee.telegram_chat_id:
        return

    deadline_str = card.deadline.strftime("%d.%m.%Y %H:%M") if card.deadline else "не указан"
    priority_map = {"low": "Низкий", "medium": "Средний", "high": "Высокий", "urgent": "Срочный"}
    creator_name = creator.name if creator else "Система"

    text = (
        f"📋 <b>Вам назначена новая задача</b>\n\n"
        f"<b>Задача:</b> {card.title}\n"
        f"<b>Дедлайн:</b> {deadline_str}\n"
        f"<b>Приоритет:</b> {priority_map.get(card.priority, card.priority)}\n"
        f"<b>Постановщик:</b> {creator_name}"
    )
    if card.description:
        text += f"\n\n{card.description[:200]}"

    ok = await _send_telegram(
        assignee.telegram_chat_id,
        text,
        _task_buttons(str(card.id), assignee_actions=True),
    )
    await _log_notification(
        db,
        card_id=card.id,
        user_id=assignee.id,
        event_type="task_created",
        status="sent" if ok else "failed",
        payload={"assignee": str(assignee.id), "creator": str(card.creator_id)},
    )


async def notify_task_assigned(
    db: AsyncSession,
    card: Card,
    new_assignee_id: object,
    assigner_id: object = None,
) -> None:
    """Уведомление новому исполнителю при смене исполнителя."""
    assignee = await _get_user(db, new_assignee_id)
    assigner = await _get_user(db, assigner_id) if assigner_id else None
    if not assignee or not assignee.telegram_chat_id:
        return

    deadline_str = card.deadline.strftime("%d.%m.%Y %H:%M") if card.deadline else "не указан"
    assigner_name = assigner.name if assigner else "Система"

    text = (
        f"🔄 <b>Вам переназначена задача</b>\n\n"
        f"<b>Задача:</b> {card.title}\n"
        f"<b>Дедлайн:</b> {deadline_str}\n"
        f"<b>Переназначил:</b> {assigner_name}"
    )
    ok = await _send_telegram(
        assignee.telegram_chat_id,
        text,
        _task_buttons(str(card.id), assignee_actions=True),
    )
    await _log_notification(
        db,
        card_id=card.id,
        user_id=assignee.id,
        event_type="task_assigned",
        status="sent" if ok else "failed",
    )


async def notify_task_completed(db: AsyncSession, card: Card) -> None:
    """Уведомление постановщику, что задача завершена."""
    if not card.creator_id:
        return
    creator = await _get_user(db, card.creator_id)
    assignee = await _get_user(db, card.assignee_id) if card.assignee_id else None
    if not creator or not creator.telegram_chat_id:
        return

    completed_str = (
        card.completed_at.strftime("%d.%m.%Y %H:%M") if card.completed_at else "только что"
    )
    assignee_name = assignee.name if assignee else "Исполнитель"

    text = (
        f"🏁 <b>Задача завершена</b>\n\n"
        f"<b>Задача:</b> {card.title}\n"
        f"<b>Исполнитель:</b> {assignee_name}\n"
        f"<b>Завершена:</b> {completed_str}"
    )
    ok = await _send_telegram(
        creator.telegram_chat_id,
        text,
        _task_buttons(str(card.id), assignee_actions=False, reviewer_actions=True),
    )
    await _log_notification(
        db,
        card_id=card.id,
        user_id=creator.id,
        event_type="task_completed",
        status="sent" if ok else "failed",
    )


async def notify_task_returned(
    db: AsyncSession, card: Card, comment: str = ""
) -> None:
    """Уведомление исполнителю, что задача возвращена в работу."""
    if not card.assignee_id:
        return
    assignee = await _get_user(db, card.assignee_id)
    if not assignee or not assignee.telegram_chat_id:
        return

    text = (
        f"🔄 <b>Задача возвращена в работу</b>\n\n"
        f"<b>Задача:</b> {card.title}"
    )
    if comment:
        text += f"\n\n<b>Комментарий:</b> {comment}"

    ok = await _send_telegram(
        assignee.telegram_chat_id,
        text,
        _task_buttons(str(card.id), assignee_actions=True),
    )
    await _log_notification(
        db,
        card_id=card.id,
        user_id=assignee.id,
        event_type="task_returned",
        status="sent" if ok else "failed",
    )


async def notify_comment_added(
    db: AsyncSession, card: Card, commenter_id: object, comment_text: str
) -> None:
    """Уведомление при добавлении комментария."""
    commenter = await _get_user(db, commenter_id)
    commenter_name = commenter.name if commenter else "Пользователь"

    # Определяем кому слать: если комментирует исполнитель — постановщику, и наоборот
    notify_user_id = None
    if card.assignee_id and str(commenter_id) == str(card.assignee_id) and card.creator_id:
        notify_user_id = card.creator_id
    elif card.creator_id and str(commenter_id) == str(card.creator_id) and card.assignee_id:
        notify_user_id = card.assignee_id

    if not notify_user_id:
        return

    target = await _get_user(db, notify_user_id)
    if not target or not target.telegram_chat_id:
        return

    text = (
        f"💬 <b>Новый комментарий по задаче</b>\n\n"
        f"<b>Задача:</b> {card.title}\n"
        f"<b>От:</b> {commenter_name}\n\n"
        f"{comment_text[:300]}"
    )
    ok = await _send_telegram(
        target.telegram_chat_id,
        text,
        _task_buttons(
            str(card.id),
            assignee_actions=str(target.id) == str(card.assignee_id),
        ),
    )
    await _log_notification(
        db,
        card_id=card.id,
        user_id=target.id,
        event_type="comment_added",
        status="sent" if ok else "failed",
    )


async def notify_deadline_reminder(
    db: AsyncSession,
    card: Card,
    event_type: str,
    escalate_to_id: object = None,
) -> None:
    """Напоминание о дедлайне.

    event_type: deadline_7d / deadline_3d / deadline_1d / deadline_due /
                deadline_overdue_1h / deadline_escalation_24h
    """
    deadline_str = card.deadline.strftime("%d.%m.%Y %H:%M") if card.deadline else ""

    labels = {
        "deadline_7d": "⏰ До дедлайна 7 дней",
        "deadline_3d": "⚠️ До дедлайна 3 дня",
        "deadline_1d": "🔴 До дедлайна 1 день",
        "deadline_due": "🚨 Дедлайн сегодня",
        "deadline_overdue_1h": "🔥 Задача просрочена",
        "deadline_escalation_24h": "🆘 Задача просрочена 24+ часа — эскалация",
    }
    label = labels.get(event_type, "Напоминание о дедлайне")

    # Уведомляем исполнителя (кроме эскалации)
    if event_type != "deadline_escalation_24h" and card.assignee_id:
        assignee = await _get_user(db, card.assignee_id)
        if assignee and assignee.telegram_chat_id:
            if not await _already_sent(db, card.id, assignee.id, event_type):
                text = (
                    f"{label}\n\n"
                    f"<b>Задача:</b> {card.title}\n"
                    f"<b>Дедлайн:</b> {deadline_str}"
                )
                ok = await _send_telegram(
                    assignee.telegram_chat_id,
                    text,
                    _task_buttons(str(card.id), assignee_actions=True),
                )
                await _log_notification(
                    db,
                    card_id=card.id,
                    user_id=assignee.id,
                    event_type=event_type,
                    status="sent" if ok else "failed",
                )

    # Эскалация руководителю
    if event_type == "deadline_escalation_24h" and escalate_to_id:
        manager = await _get_user(db, escalate_to_id)
        if manager and manager.telegram_chat_id:
            if not await _already_sent(db, card.id, manager.id, event_type):
                assignee = (
                    await _get_user(db, card.assignee_id) if card.assignee_id else None
                )
                assignee_name = assignee.name if assignee else "Неизвестен"
                text = (
                    f"🆘 <b>Эскалация: задача просрочена 24+ часа</b>\n\n"
                    f"<b>Задача:</b> {card.title}\n"
                    f"<b>Дедлайн был:</b> {deadline_str}\n"
                    f"<b>Исполнитель:</b> {assignee_name}"
                )
                ok = await _send_telegram(manager.telegram_chat_id, text)
                await _log_notification(
                    db,
                    card_id=card.id,
                    user_id=manager.id,
                    event_type=event_type,
                    status="sent" if ok else "failed",
                )
