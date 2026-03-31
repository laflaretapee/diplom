from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import date

from celery import Task
from redis.asyncio import Redis
from sqlalchemy import select

from backend.app.celery_app import celery_app
from backend.app.core.config import get_settings
from backend.app.core.telegram import send_telegram_message
from backend.app.db import models as _db_models  # noqa: F401
from backend.app.db.session import SessionLocal
from backend.app.models.franchisee import Franchisee
from backend.app.models.franchisee_task import FranchiseeTask, TaskStatus
from backend.app.models.ingredient import Ingredient
from backend.app.models.point import Point
from backend.app.models.user import User, UserRole
from backend.app.models.user_point import UserPoint
from backend.app.modules.notifications.service import notification_enabled

logger = logging.getLogger(__name__)
_TASK_LOOP: asyncio.AbstractEventLoop | None = None


class NotificationTask(Task):
    abstract = True
    max_retries = 3
    default_retry_delay = 60


def _run_async(awaitable):
    global _TASK_LOOP
    if _TASK_LOOP is None or _TASK_LOOP.is_closed():
        _TASK_LOOP = asyncio.new_event_loop()
        asyncio.set_event_loop(_TASK_LOOP)
    return _TASK_LOOP.run_until_complete(awaitable)


async def _get_point_manager_context(
    point_id: str,
    notification_type: str,
) -> tuple[str, list[str]]:
    async with SessionLocal() as db:
        point = (
            await db.execute(select(Point).where(Point.id == uuid.UUID(point_id)))
        ).scalar_one_or_none()
        result = await db.execute(
            select(User)
            .join(UserPoint, UserPoint.user_id == User.id)
            .where(
                UserPoint.point_id == uuid.UUID(point_id),
                User.role == UserRole.POINT_MANAGER,
                User.is_active.is_(True),
                User.telegram_chat_id.is_not(None),
            )
        )
        users = result.scalars().all()
        recipients = [
            user.telegram_chat_id
            for user in users
            if user.telegram_chat_id and notification_enabled(user, notification_type)
        ]
        return (point.name if point is not None else point_id, recipients)


async def _get_low_stock_context(
    ingredient_id: str,
    point_id: str,
) -> tuple[str, str, str | None, list[str]]:
    async with SessionLocal() as db:
        ingredient = (
            await db.execute(
                select(Ingredient).where(Ingredient.id == uuid.UUID(ingredient_id))
            )
        ).scalar_one_or_none()
        point_name, recipients = await _get_point_manager_context(point_id, "low_stock")
        ingredient_name = ingredient.name if ingredient is not None else ingredient_id
        unit = ingredient.unit if ingredient is not None else None
        return point_name, ingredient_name, unit, recipients


async def _get_franchisee_owner_context(
    franchisee_id: str,
    notification_type: str,
) -> tuple[Franchisee | None, list[str]]:
    async with SessionLocal() as db:
        franchisee = (
            await db.execute(
                select(Franchisee).where(Franchisee.id == uuid.UUID(franchisee_id))
            )
        ).scalar_one_or_none()
        if franchisee is None or franchisee.responsible_owner_id is None:
            return None, []

        owner = (
            await db.execute(
                select(User).where(
                    User.id == franchisee.responsible_owner_id,
                    User.is_active.is_(True),
                    User.telegram_chat_id.is_not(None),
                )
            )
        ).scalar_one_or_none()
        if owner is None or not notification_enabled(owner, notification_type):
            return franchisee, []
        return franchisee, [owner.telegram_chat_id]


async def _get_franchisee_task_context(
    franchisee_id: str,
    task_id: str,
    notification_type: str,
) -> tuple[Franchisee | None, FranchiseeTask | None, list[str]]:
    async with SessionLocal() as db:
        task = (
            await db.execute(
                select(FranchiseeTask).where(
                    FranchiseeTask.id == uuid.UUID(task_id),
                    FranchiseeTask.franchisee_id == uuid.UUID(franchisee_id),
                )
            )
        ).scalar_one_or_none()
        if task is None:
            return None, None, []

        franchisee, recipients = await _get_franchisee_owner_context(
            franchisee_id,
            notification_type,
        )
        return franchisee, task, recipients


async def _collect_overdue_task_notifications() -> list[dict[str, str]]:
    settings = get_settings()
    redis = Redis.from_url(settings.redis_url, decode_responses=True)
    try:
        async with SessionLocal() as db:
            result = await db.execute(
                select(FranchiseeTask, Franchisee, User)
                .join(Franchisee, FranchiseeTask.franchisee_id == Franchisee.id)
                .join(User, Franchisee.responsible_owner_id == User.id)
                .where(
                    FranchiseeTask.due_date.is_not(None),
                    FranchiseeTask.due_date < date.today(),
                    FranchiseeTask.status.in_([TaskStatus.PENDING, TaskStatus.IN_PROGRESS]),
                    User.is_active.is_(True),
                    User.telegram_chat_id.is_not(None),
                )
            )
            payloads: list[dict[str, str]] = []
            for task, franchisee, user in result.all():
                if not notification_enabled(user, "franchisee_task_overdue"):
                    continue
                dedupe_key = f"task-overdue:{task.id}:{task.status.value}"
                if not await redis.set(dedupe_key, "1", ex=86400, nx=True):
                    continue
                payloads.append(
                    {
                        "task_id": str(task.id),
                        "title": task.title,
                        "due_date": task.due_date.isoformat() if task.due_date else "",
                        "company_name": franchisee.company_name,
                        "chat_id": user.telegram_chat_id or "",
                    }
                )
            return payloads
    finally:
        await redis.aclose()


async def _collect_weekly_report_payloads() -> list[dict[str, str]]:
    from backend.app.modules.analytics.service import build_weekly_revenue_report_message

    async with SessionLocal() as db:
        result = await db.execute(
            select(User).where(
                User.role.in_([UserRole.SUPER_ADMIN, UserRole.FRANCHISEE]),
                User.is_active.is_(True),
                User.telegram_chat_id.is_not(None),
            )
        )
        users = result.scalars().all()
        payloads: list[dict[str, str]] = []
        for user in users:
            if not notification_enabled(user, "weekly_revenue_report"):
                continue
            message = await build_weekly_revenue_report_message(user=user, db=db)
            if not message:
                continue
            payloads.append(
                {
                    "user_id": str(user.id),
                    "chat_id": user.telegram_chat_id or "",
                    "message": message,
                }
            )
        return payloads


def _short_id(value: str) -> str:
    return value.split("-", maxsplit=1)[0].upper()


def _deliver_message(chat_ids: list[str], message: str) -> list[dict[str, object]]:
    deliveries: list[dict[str, object]] = []
    for chat_id in chat_ids:
        sent = _run_async(send_telegram_message(chat_id, message))
        deliveries.append({"chat_id": chat_id, "sent": sent})
    return deliveries


def _build_order_message(
    event_type: str,
    order_id: str,
    point_name: str,
    total_amount: str | None,
    status: str | None,
) -> str:
    short_id = _short_id(order_id)
    if event_type == "order_cancelled":
        return f"Заказ #{short_id} на точке {point_name} отменён."
    if event_type == "order_status_changed":
        return f"Заказ #{short_id} на точке {point_name} изменил статус: {status or 'updated'}."
    return f"Новый заказ #{short_id} на точке {point_name} на сумму {total_amount or '0.00'} ₽."


@celery_app.task(
    bind=True,
    base=NotificationTask,
    name="notifications.send_order_notification",
)
def send_order_notification(
    self,
    order_id: str,
    point_id: str,
    event_type: str,
    recipients: list[str] | None = None,
    total_amount: str | None = None,
    status: str | None = None,
):
    try:
        preference_key = "order_cancelled" if event_type == "order_cancelled" else "order_created"
        point_name, filtered_recipients = _run_async(
            _get_point_manager_context(point_id, preference_key)
        )
        resolved_recipients = recipients or filtered_recipients
        if not resolved_recipients:
            logger.info(
                "Skipping %s notification for order %s: no recipients",
                event_type,
                order_id,
            )
            return {
                "status": "skipped",
                "reason": "no_recipients",
                "order_id": order_id,
                "event": event_type,
            }

        message = _build_order_message(
            event_type=event_type,
            order_id=order_id,
            point_name=point_name,
            total_amount=total_amount,
            status=status,
        )
        logger.info(
            "Sending %s notification for order %s to %s",
            event_type,
            order_id,
            resolved_recipients,
        )
        delivered = _deliver_message(resolved_recipients, message)
        logger.info("Notification sent: order=%s event=%s", order_id, event_type)
        return {
            "status": "sent",
            "order_id": order_id,
            "event": event_type,
            "recipients": delivered,
        }
    except Exception as exc:
        logger.error("Failed to send notification: %s", exc)
        raise self.retry(exc=exc)


@celery_app.task(
    bind=True,
    base=NotificationTask,
    name="notifications.send_low_stock_notification",
)
def send_low_stock_notification(
    self,
    ingredient_id: str,
    point_id: str,
    current_qty: float,
    min_qty: float,
):
    try:
        point_name, ingredient_name, unit, recipients = _run_async(
            _get_low_stock_context(ingredient_id, point_id)
        )
        if not recipients:
            logger.info(
                "Skipping low_stock notification for ingredient=%s point=%s: no recipients",
                ingredient_id,
                point_id,
            )
            return {"status": "skipped", "type": "low_stock", "reason": "no_recipients"}

        suffix = f" {unit}" if unit else ""
        message = (
            f"Низкий остаток: {ingredient_name} на точке {point_name}. "
            f"Текущий остаток {current_qty}{suffix}, минимум {min_qty}{suffix}."
        )
        delivered = _deliver_message(recipients, message)
        logger.info(
            "Low stock alert delivered: ingredient=%s point=%s recipients=%s",
            ingredient_id,
            point_id,
            recipients,
        )
        return {
            "status": "sent",
            "type": "low_stock",
            "ingredient_id": ingredient_id,
            "point_id": point_id,
            "recipients": delivered,
        }
    except Exception as exc:
        raise self.retry(exc=exc)


@celery_app.task(
    bind=True,
    base=NotificationTask,
    name="notifications.send_franchisee_stage_notification",
)
def send_franchisee_stage_notification(self, franchisee_id: str, new_status: str):
    try:
        franchisee, recipients = _run_async(
            _get_franchisee_owner_context(franchisee_id, "franchisee_stage_changed")
        )
        if franchisee is None or not recipients:
            return {
                "status": "skipped",
                "type": "franchisee_stage_changed",
                "reason": "no_recipients",
            }

        message = f"Франчайзи {franchisee.company_name} переведён на стадию {new_status}."
        delivered = _deliver_message(recipients, message)
        logger.info(
            "Franchisee stage notification sent: franchisee=%s status=%s recipients=%s",
            franchisee_id,
            new_status,
            recipients,
        )
        return {
            "status": "sent",
            "type": "franchisee_stage_changed",
            "franchisee_id": franchisee_id,
            "recipients": delivered,
        }
    except Exception as exc:
        logger.error("Failed to send franchisee stage notification: %s", exc)
        raise self.retry(exc=exc)


@celery_app.task(
    bind=True,
    base=NotificationTask,
    name="notifications.send_franchisee_task_status_notification",
)
def send_franchisee_task_status_notification(
    self,
    franchisee_id: str,
    task_id: str,
    new_status: str,
):
    try:
        franchisee, task, recipients = _run_async(
            _get_franchisee_task_context(
                franchisee_id,
                task_id,
                "franchisee_task_changed",
            )
        )
        if franchisee is None or task is None or not recipients:
            return {
                "status": "skipped",
                "type": "franchisee_task_changed",
                "reason": "no_recipients",
            }

        message = (
            f"Задача онбординга '{task.title}' у франчайзи {franchisee.company_name} "
            f"получила статус {new_status}."
        )
        delivered = _deliver_message(recipients, message)
        logger.info(
            "Franchisee task notification sent: task=%s status=%s recipients=%s",
            task_id,
            new_status,
            recipients,
        )
        return {
            "status": "sent",
            "type": "franchisee_task_changed",
            "task_id": task_id,
            "recipients": delivered,
        }
    except Exception as exc:
        logger.error("Failed to send franchisee task notification: %s", exc)
        raise self.retry(exc=exc)


@celery_app.task(
    bind=True,
    base=NotificationTask,
    name="notifications.send_overdue_franchisee_task_notifications",
)
def send_overdue_franchisee_task_notifications(self):
    try:
        payloads = _run_async(_collect_overdue_task_notifications())
        if not payloads:
            logger.info("No overdue franchisee tasks to notify")
            return {"status": "skipped", "type": "franchisee_task_overdue", "count": 0}

        deliveries = []
        for payload in payloads:
            message = (
                f"Просрочена задача '{payload['title']}' у франчайзи "
                f"{payload['company_name']}. Срок: {payload['due_date']}."
            )
            deliveries.extend(_deliver_message([payload["chat_id"]], message))
        logger.info("Overdue franchisee task notifications sent: count=%s", len(payloads))
        return {
            "status": "sent",
            "type": "franchisee_task_overdue",
            "count": len(payloads),
            "recipients": deliveries,
        }
    except Exception as exc:
        logger.error("Failed to send overdue franchisee task notifications: %s", exc)
        raise self.retry(exc=exc)


@celery_app.task(
    bind=True,
    base=NotificationTask,
    name="notifications.send_weekly_revenue_report",
)
def send_weekly_revenue_report(self):
    try:
        payloads = _run_async(_collect_weekly_report_payloads())
        if not payloads:
            logger.info("No weekly revenue reports to deliver")
            return {
                "status": "skipped",
                "type": "weekly_revenue_report",
                "count": 0,
            }

        deliveries = []
        for payload in payloads:
            deliveries.extend(_deliver_message([payload["chat_id"]], payload["message"]))
        logger.info("Weekly revenue reports sent: count=%s", len(payloads))
        return {
            "status": "sent",
            "type": "weekly_revenue_report",
            "count": len(payloads),
            "recipients": deliveries,
        }
    except Exception as exc:
        logger.error("Failed to send weekly revenue reports: %s", exc)
        raise self.retry(exc=exc)
