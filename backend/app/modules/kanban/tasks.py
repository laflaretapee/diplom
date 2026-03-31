"""Celery tasks for the Kanban module."""
from __future__ import annotations

import asyncio
import logging
import uuid
from collections.abc import AsyncIterator
from datetime import datetime, timezone

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend.app.celery_app import celery_app
from backend.app.core.config import get_settings
from backend.app.core.telegram import send_telegram_message
from backend.app.models.user import User
from backend.app.modules.kanban.models import Board, Card
from backend.app.modules.notifications.service import notification_enabled

logger = logging.getLogger(__name__)


def _run_async(awaitable):
    return asyncio.run(awaitable)


async def _get_task_session() -> AsyncIterator:
    engine = create_async_engine(get_settings().database_url, echo=False)
    session_factory = async_sessionmaker(bind=engine, expire_on_commit=False)
    try:
        async with session_factory() as session:
            yield session
    finally:
        await engine.dispose()


async def _get_card_and_assignee(
    card_id: str, assignee_id: str
) -> tuple[Card | None, User | None, str | None]:
    async for db in _get_task_session():
        card_result = await db.execute(
            select(Card, Board.name)
            .join(Board, Board.id == Card.board_id)
            .where(Card.id == uuid.UUID(card_id))
        )
        card_row = card_result.one_or_none()
        if card_row is None:
            return None, None, None
        card, board_name = card_row
        user = (
            await db.execute(
                select(User).where(
                    User.id == uuid.UUID(assignee_id),
                    User.is_active.is_(True),
                )
            )
        ).scalar_one_or_none()
        return card, user, board_name


async def _get_card_with_assignee(card_id: str) -> tuple[Card | None, User | None, str | None]:
    async for db in _get_task_session():
        card_result = await db.execute(
            select(Card, Board.name)
            .join(Board, Board.id == Card.board_id)
            .where(Card.id == uuid.UUID(card_id))
        )
        card_row = card_result.one_or_none()
        if card_row is None:
            return None, None, None
        card, board_name = card_row
        if card is None or card.assignee_id is None:
            return card, None, board_name
        user = (
            await db.execute(
                select(User).where(
                    User.id == card.assignee_id,
                    User.is_active.is_(True),
                )
            )
        ).scalar_one_or_none()
        return card, user, board_name


async def _send_assigned(card_id: str, assignee_id: str) -> None:
    card, user, board_name = await _get_card_and_assignee(card_id, assignee_id)
    if card is None or user is None:
        return
    if not user.telegram_chat_id:
        logger.warning(
            "Skipping assigned notification for card %s: user %s has no telegram_chat_id",
            card_id,
            assignee_id,
        )
        return
    if not notification_enabled(user, "kanban_card_assigned"):
        return
    msg = (
        f"📋 Вам назначена карточка:\n"
        f"*{card.title}*\n"
        f"Доска: {board_name or 'Kanban'}\n"
        f"Приоритет: {card.priority}"
    )
    if card.deadline:
        msg += f"\nДедлайн: {card.deadline.strftime('%d.%m.%Y %H:%M')}"
    await send_telegram_message(user.telegram_chat_id, msg)


async def _send_deadline(card_id: str) -> None:
    card, user, board_name = await _get_card_with_assignee(card_id)
    if card is None or user is None:
        return
    if not user.telegram_chat_id:
        logger.warning(
            "Skipping deadline notification for card %s: user %s has no telegram_chat_id",
            card_id,
            user.id,
        )
        return
    if not notification_enabled(user, "kanban_card_deadline"):
        return
    deadline_str = card.deadline.strftime("%d.%m.%Y %H:%M") if card.deadline else "не задан"
    msg = (
        f"⏰ Напоминание о дедлайне!\n"
        f"Карточка: *{card.title}*\n"
        f"Доска: {board_name or 'Kanban'}\n"
        f"Дедлайн: {deadline_str}"
    )
    await send_telegram_message(user.telegram_chat_id, msg)


async def _check_overdue() -> None:
    now = datetime.now(tz=timezone.utc)
    async for db in _get_task_session():
        result = await db.execute(
            select(Card).where(
                Card.deadline.is_not(None),
                Card.deadline < now,
                Card.assignee_id.is_not(None),
            )
        )
        overdue_cards = result.scalars().all()

        for card in overdue_cards:
            board_result = await db.execute(select(Board.name).where(Board.id == card.board_id))
            board_name = board_result.scalar_one_or_none() or "Kanban"
            user_result = await db.execute(
                select(User).where(
                    User.id == card.assignee_id,
                    User.is_active.is_(True),
                )
            )
            user = user_result.scalar_one_or_none()
            if user is None:
                continue
            if not user.telegram_chat_id:
                logger.warning(
                    "Skipping overdue notification for card %s: user %s has no telegram_chat_id",
                    card.id,
                    user.id,
                )
                continue
            if not notification_enabled(user, "kanban_card_overdue"):
                continue
            deadline_str = card.deadline.strftime("%d.%m.%Y %H:%M") if card.deadline else ""
            msg = (
                f"🚨 Карточка просрочена!\n"
                f"*{card.title}*\n"
                f"Доска: {board_name}\n"
                f"Дедлайн был: {deadline_str}"
            )
            try:
                await send_telegram_message(user.telegram_chat_id, msg)
            except Exception:
                logger.exception("Failed to send overdue notification for card %s", card.id)


async def _process_outbox() -> None:
    async for db in _get_task_session():
        result = await db.execute(
            text(
                "SELECT id FROM domain_events "
                "WHERE status = 'pending' "
                "ORDER BY created_at LIMIT 100"
            )
        )
        rows = result.fetchall()
        if not rows:
            return
        ids = [str(row[0]) for row in rows]
        placeholders = ", ".join(f"'{eid}'" for eid in ids)
        await db.execute(
            text(
                f"UPDATE domain_events SET status = 'published', published_at = now() "
                f"WHERE id IN ({placeholders})"
            )
        )
        await db.commit()
        logger.info("Processed %d outbox events", len(ids))


@celery_app.task(
    name="app.modules.kanban.tasks.send_card_assigned_notification",
    max_retries=3,
    default_retry_delay=60,
)
def send_card_assigned_notification(card_id: str, assignee_id: str) -> None:
    try:
        _run_async(_send_assigned(card_id, assignee_id))
    except Exception as exc:
        logger.exception("send_card_assigned_notification failed for card %s", card_id)
        raise send_card_assigned_notification.retry(exc=exc) from exc


@celery_app.task(
    name="app.modules.kanban.tasks.send_card_deadline_notification",
    max_retries=3,
    default_retry_delay=60,
)
def send_card_deadline_notification(card_id: str) -> None:
    try:
        _run_async(_send_deadline(card_id))
    except Exception as exc:
        logger.exception("send_card_deadline_notification failed for card %s", card_id)
        raise send_card_deadline_notification.retry(exc=exc) from exc


@celery_app.task(
    name="app.modules.kanban.tasks.send_card_deadline_set_notification",
    max_retries=3,
    default_retry_delay=60,
)
def send_card_deadline_set_notification(card_id: str) -> None:
    send_card_deadline_notification(card_id)


@celery_app.task(name="app.modules.kanban.tasks.check_overdue_cards")
def check_overdue_cards() -> None:
    try:
        _run_async(_check_overdue())
    except Exception:
        logger.exception("check_overdue_cards failed")


@celery_app.task(name="app.modules.kanban.tasks.process_outbox_events")
def process_outbox_events() -> None:
    try:
        _run_async(_process_outbox())
    except Exception:
        logger.exception("process_outbox_events failed")
