from __future__ import annotations

import logging
import random
import re
import uuid
from decimal import Decimal, InvalidOperation

from fastapi import HTTPException, status
from redis.asyncio import Redis
from sqlalchemy import or_, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.config import get_settings
from backend.app.core.telegram import send_telegram_message
from backend.app.models.ingredient import Ingredient
from backend.app.models.order import Order, OrderStatus
from backend.app.models.point import Point
from backend.app.models.stock_item import StockItem
from backend.app.models.user import User
from backend.app.models.user_point import UserPoint
from backend.app.modules.notifications.schemas import (
    NotificationPreferences,
    NotificationPreferencesUpdate,
    NotificationsModuleStatus,
    TelegramCommand,
    TelegramLinkResponse,
    TelegramStatusResponse,
    TelegramWebhookUpdate,
)
from backend.app.modules.orders.schemas import OrderStatusUpdate
from backend.app.modules.orders.service import update_order_status
from backend.app.modules.warehouse.schemas import SupplyCreate
from backend.app.modules.warehouse.service import create_supply

logger = logging.getLogger(__name__)

LINK_CODE_TTL_SECONDS = 300
LINK_CODE_RE = re.compile(r"^/link(?:@[A-Za-z0-9_]+)?\s+(\d{6})\s*$")
MOCK_COMMAND_NAMES = {
    "start",
    "link",
    "orders",
    "order",
    "tasks",
    "stock",
    "stock_add",
    "low_stock",
}
DEFAULT_NOTIFICATION_PREFERENCES = NotificationPreferences().model_dump()
LINK_REQUIRED_TEXT = (
    "Сначала привяжите аккаунт: получите код в приложении и отправьте /link <код>."
)


def get_status() -> NotificationsModuleStatus:
    return NotificationsModuleStatus(module="notifications", status="active")


async def _get_redis() -> Redis:
    settings = get_settings()
    return Redis.from_url(settings.redis_url, decode_responses=True)


async def generate_link_code(user_id: uuid.UUID) -> TelegramLinkResponse:
    redis = await _get_redis()
    try:
        for _ in range(10):
            code = f"{random.randint(0, 999999):06d}"
            key = f"tg_link:{code}"
            if await redis.set(key, str(user_id), ex=LINK_CODE_TTL_SECONDS, nx=True):
                return TelegramLinkResponse(
                    code=code,
                    expires_in=LINK_CODE_TTL_SECONDS,
                    instructions=f"Отправьте боту: /link {code}",
                )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Could not allocate Telegram link code",
        )
    finally:
        await redis.aclose()


def get_telegram_status(user: User) -> TelegramStatusResponse:
    return TelegramStatusResponse(
        linked=bool(user.telegram_chat_id),
        chat_id=user.telegram_chat_id,
    )


def get_notification_preferences(user: User) -> NotificationPreferences:
    raw = user.notification_settings if isinstance(user.notification_settings, dict) else {}
    merged = DEFAULT_NOTIFICATION_PREFERENCES.copy()
    for key, value in raw.items():
        if key in merged:
            merged[key] = bool(value)
    return NotificationPreferences(**merged)


def notification_enabled(user: User, notification_type: str) -> bool:
    preferences = get_notification_preferences(user).model_dump()
    return bool(preferences.get(notification_type, True))


async def update_notification_preferences(
    user: User,
    payload: NotificationPreferencesUpdate,
    db: AsyncSession,
) -> NotificationPreferences:
    preferences = get_notification_preferences(user).model_dump()
    preferences.update(payload.model_dump(exclude_none=True))
    user.notification_settings = preferences
    await db.commit()
    await db.refresh(user)
    return NotificationPreferences(**preferences)


async def unlink_telegram(user: User, db: AsyncSession) -> None:
    user.telegram_chat_id = None
    await db.commit()


def parse_telegram_command_text(text: str | None) -> TelegramCommand | None:
    if text is None:
        return None

    parts = text.strip().split()
    if not parts:
        return None

    raw_name = parts[0]
    has_slash = raw_name.startswith("/")
    if has_slash:
        raw_name = raw_name[1:]
    command_name = raw_name.split("@", maxsplit=1)[0].lower()
    if command_name not in MOCK_COMMAND_NAMES:
        return None
    if not has_slash and command_name not in MOCK_COMMAND_NAMES:
        return None
    return TelegramCommand(name=command_name, args=parts[1:])


def _extract_incoming_chat_and_text(update: TelegramWebhookUpdate) -> tuple[str, str] | None:
    if update.message is not None and update.message.text:
        return str(update.message.chat.id), update.message.text

    callback_query = update.callback_query
    if (
        callback_query is not None
        and callback_query.data
        and callback_query.message is not None
    ):
        return str(callback_query.message.chat.id), callback_query.data

    return None


def _short_uuid(value: uuid.UUID) -> str:
    return str(value).split("-", maxsplit=1)[0].upper()


def _format_decimal(value: Decimal) -> str:
    text = format(value, "f")
    return text.rstrip("0").rstrip(".") or "0"


def _build_help_text(user_name: str) -> str:
    return "\n".join(
        [
            f"Добро пожаловать в Джейсан, {user_name}!",
            "",
            "Telegram mock-команды:",
            "/orders",
            "/order <order_id> <status>",
            "/tasks",
            "/stock",
            "/stock_add <ingredient_id> <qty>",
            "/low_stock",
        ]
    )


def _build_main_menu_markup() -> dict[str, list[list[dict[str, str]]]]:
    return {
        "inline_keyboard": [
            [
                {"text": "📦 Заказы", "callback_data": "orders"},
                {"text": "📋 Задачи", "callback_data": "tasks"},
            ],
            [
                {"text": "🏪 Склад", "callback_data": "stock"},
                {"text": "⚠️ Low Stock", "callback_data": "low_stock"},
            ],
        ]
    }


async def _find_user_by_chat_id(chat_id: str, db: AsyncSession) -> User | None:
    result = await db.execute(select(User).where(User.telegram_chat_id == chat_id))
    return result.scalar_one_or_none()


async def _get_user_points(user_id: uuid.UUID, db: AsyncSession) -> list[tuple[uuid.UUID, str]]:
    result = await db.execute(
        select(Point.id, Point.name)
        .join(UserPoint, UserPoint.point_id == Point.id)
        .where(UserPoint.user_id == user_id)
        .order_by(Point.name)
    )
    return [(point_id, point_name) for point_id, point_name in result.all()]


async def _handle_link_command(chat_id: str, code: str, db: AsyncSession) -> None:
    redis = await _get_redis()
    try:
        user_id = await redis.get(f"tg_link:{code}")
        if user_id is None:
            await send_telegram_message(chat_id, "Код недействителен или истёк.")
            return

        result = await db.execute(select(User).where(User.id == uuid.UUID(user_id)))
        user = result.scalar_one_or_none()
        if user is None:
            await redis.delete(f"tg_link:{code}")
            return

        user.telegram_chat_id = chat_id
        await db.commit()
        await redis.delete(f"tg_link:{code}")
        await send_telegram_message(chat_id, "Аккаунт успешно привязан!")
        logger.info("Linked telegram chat %s to user %s", chat_id, user.id)
    finally:
        await redis.aclose()


async def _handle_orders_command(user: User, db: AsyncSession) -> str:
    result = await db.execute(
        select(Order, Point)
        .join(Point, Point.id == Order.point_id)
        .join(UserPoint, UserPoint.point_id == Order.point_id)
        .where(UserPoint.user_id == user.id)
        .order_by(Order.created_at.desc())
        .limit(10)
    )
    rows = result.all()
    if not rows:
        return "Заказов по вашим точкам пока нет."

    lines = ["Последние заказы:"]
    for order, point in rows:
        lines.append(
            "• "
            f"#{_short_uuid(order.id)} | {point.name} | {order.status.value} | "
            f"{_format_decimal(order.total_amount)} ₽"
        )
    return "\n".join(lines)


async def _handle_order_command(user: User, args: list[str], db: AsyncSession) -> str:
    if len(args) != 2:
        statuses = ", ".join(status.value for status in OrderStatus)
        return f"Использование: /order <order_id> <status>. Статусы: {statuses}."

    raw_order_id, raw_status = args
    try:
        order_id = uuid.UUID(raw_order_id)
    except ValueError:
        return "Неверный order_id. Ожидается UUID."

    try:
        next_status = OrderStatus(raw_status.lower())
    except ValueError:
        statuses = ", ".join(status.value for status in OrderStatus)
        return f"Неизвестный статус. Используйте: {statuses}."

    result = await db.execute(
        select(Order)
        .join(UserPoint, UserPoint.point_id == Order.point_id)
        .where(
            Order.id == order_id,
            UserPoint.user_id == user.id,
        )
    )
    order = result.scalar_one_or_none()
    if order is None:
        return "Заказ не найден или недоступен."

    try:
        updated = await update_order_status(
            order_id=order.id,
            data=OrderStatusUpdate(status=next_status),
            db=db,
        )
    except HTTPException as exc:
        return str(exc.detail)

    return f"Статус заказа #{_short_uuid(updated.id)} обновлён: {updated.status.value}."


async def _handle_tasks_command(user: User, db: AsyncSession) -> str:
    from backend.app.modules.kanban.models import Board, BoardColumn, Card

    try:
        result = await db.execute(
            select(Card, BoardColumn, Board)
            .join(BoardColumn, BoardColumn.id == Card.column_id)
            .join(Board, Board.id == Card.board_id)
            .where(
                or_(
                    Card.assignee_id == user.id,
                    Board.owner_id == user.id,
                )
            )
            .order_by(Card.updated_at.desc())
            .limit(8)
        )
    except SQLAlchemyError:
        logger.exception("Failed to read kanban cards for telegram user %s", user.id)
        return "Kanban-задачи сейчас недоступны в этом окружении."

    rows = result.all()
    if not rows:
        return "Задач в kanban для вас пока нет."

    lines = ["Задачи из kanban:"]
    for card, column, board in rows:
        details = [f"{board.name} / {column.name}", f"priority {card.priority}"]
        if card.deadline is not None:
            details.append(f"deadline {card.deadline.date().isoformat()}")
        lines.append(f"• {card.title} ({'; '.join(details)})")
    return "\n".join(lines)


async def _handle_stock_command(user: User, db: AsyncSession) -> str:
    result = await db.execute(
        select(StockItem, Ingredient, Point)
        .join(Ingredient, Ingredient.id == StockItem.ingredient_id)
        .join(Point, Point.id == StockItem.point_id)
        .join(UserPoint, UserPoint.point_id == StockItem.point_id)
        .where(UserPoint.user_id == user.id)
        .order_by(Point.name, Ingredient.name)
        .limit(12)
    )
    rows = result.all()
    if not rows:
        return "Складских остатков по вашим точкам пока нет."

    lines = ["Остатки по складу:"]
    for stock_item, ingredient, point in rows:
        marker = " LOW" if stock_item.quantity < ingredient.min_stock_level else ""
        lines.append(
            "• "
            f"{point.name}: {ingredient.name} "
            f"{_format_decimal(stock_item.quantity)} {ingredient.unit} "
            f"(min {_format_decimal(ingredient.min_stock_level)}){marker}"
        )
    return "\n".join(lines)


async def _resolve_supply_point(
    user: User,
    ingredient_id: uuid.UUID,
    db: AsyncSession,
) -> tuple[tuple[uuid.UUID, str] | None, str | None]:
    points = await _get_user_points(user.id, db)
    if not points:
        return None, "За вами не закреплены точки."

    result = await db.execute(
        select(Point.id, Point.name)
        .join(StockItem, StockItem.point_id == Point.id)
        .join(UserPoint, UserPoint.point_id == Point.id)
        .where(
            UserPoint.user_id == user.id,
            StockItem.ingredient_id == ingredient_id,
        )
        .order_by(Point.name)
    )
    stock_points = result.all()
    if len(stock_points) == 1:
        point_id, point_name = stock_points[0]
        return (point_id, point_name), None

    if len(points) == 1:
        return points[0], None

    if len(stock_points) > 1:
        return (
            None,
            "Ингредиент найден в нескольких точках. Для Sprint 1 /stock_add работает "
            "только при однозначно определяемой точке.",
        )

    return (
        None,
        "За вами закреплено несколько точек. Для Sprint 1 /stock_add работает "
        "только при одной доступной точке.",
    )


async def _handle_stock_add_command(user: User, args: list[str], db: AsyncSession) -> str:
    if len(args) != 2:
        return "Использование: /stock_add <ingredient_id> <qty>."

    raw_ingredient_id, raw_quantity = args
    try:
        ingredient_id = uuid.UUID(raw_ingredient_id)
    except ValueError:
        return "Неверный ingredient_id. Ожидается UUID."

    try:
        quantity = Decimal(raw_quantity)
    except InvalidOperation:
        return "Неверное количество. Используйте число, например 1.5."
    if quantity <= 0:
        return "Количество должно быть больше 0."

    result = await db.execute(select(Ingredient).where(Ingredient.id == ingredient_id))
    ingredient = result.scalar_one_or_none()
    if ingredient is None:
        return "Ингредиент не найден."

    point_row, error_text = await _resolve_supply_point(user, ingredient_id, db)
    if point_row is None:
        return error_text or "Не удалось определить точку для пополнения."

    point_id, point_name = point_row
    try:
        supply = await create_supply(
            SupplyCreate(
                point_id=point_id,
                ingredient_id=ingredient_id,
                quantity=quantity,
                supplier_name="Telegram mock",
                note="Sprint 1 stock_add command",
            ),
            created_by_id=user.id,
            db=db,
        )
    except HTTPException as exc:
        return str(exc.detail)

    return (
        f"Остаток обновлён: {ingredient.name} +{_format_decimal(quantity)} {ingredient.unit} "
        f"на точке {point_name}. Новый остаток: {_format_decimal(supply.new_quantity)} "
        f"{ingredient.unit}."
    )


async def _handle_low_stock_command(user: User, db: AsyncSession) -> str:
    result = await db.execute(
        select(StockItem, Ingredient, Point)
        .join(Ingredient, Ingredient.id == StockItem.ingredient_id)
        .join(Point, Point.id == StockItem.point_id)
        .join(UserPoint, UserPoint.point_id == StockItem.point_id)
        .where(
            UserPoint.user_id == user.id,
            StockItem.quantity < Ingredient.min_stock_level,
        )
        .order_by(Point.name, Ingredient.name)
        .limit(12)
    )
    rows = result.all()
    if not rows:
        return "Позиции ниже минимального остатка не найдены."

    lines = ["Низкие остатки:"]
    for stock_item, ingredient, point in rows:
        lines.append(
            "• "
            f"{point.name}: {ingredient.name} "
            f"{_format_decimal(stock_item.quantity)} / "
            f"{_format_decimal(ingredient.min_stock_level)} "
            f"{ingredient.unit}"
        )
    return "\n".join(lines)


async def _handle_linked_command(
    command: TelegramCommand,
    user: User,
    db: AsyncSession,
) -> str:
    if command.name == "orders":
        return await _handle_orders_command(user, db)
    if command.name == "order":
        return await _handle_order_command(user, command.args, db)
    if command.name == "tasks":
        return await _handle_tasks_command(user, db)
    if command.name == "stock":
        return await _handle_stock_command(user, db)
    if command.name == "stock_add":
        return await _handle_stock_add_command(user, command.args, db)
    if command.name == "low_stock":
        return await _handle_low_stock_command(user, db)
    return _build_help_text(user.name)


async def _handle_task_callback(
    db: AsyncSession, callback_data: str, chat_id: str
) -> str:
    """Обработка inline кнопок задач из Telegram."""
    from datetime import UTC, datetime

    from backend.app.modules.kanban.models import Card
    from backend.app.modules.kanban.notifications import notify_task_completed, notify_task_returned
    from backend.app.modules.kanban.state_machine import can_transition

    parts = callback_data.split(":", 1)
    if len(parts) != 2:
        return "❓ Неизвестное действие"
    action, card_id = parts

    user_result = await db.execute(
        select(User).where(User.telegram_chat_id == chat_id)
    )
    user = user_result.scalar_one_or_none()
    if not user:
        return "❌ Ваш аккаунт не привязан к CRM. Используйте /link"

    card_result = await db.execute(select(Card).where(Card.id == uuid.UUID(card_id)))
    card = card_result.scalar_one_or_none()
    if not card:
        return "❌ Задача не найдена"

    now = datetime.now(UTC)

    if action == "task_accept":
        if str(user.id) != str(card.assignee_id):
            return "❌ Вы не являетесь исполнителем этой задачи"
        if not can_transition(card.status, "in_progress"):
            return f"❌ Нельзя перевести из '{card.status}' в 'in_progress'"
        card.status = "in_progress"
        card.accepted_at = now
        await db.commit()
        return "✅ Задача принята, переведена в работу"

    elif action == "task_start":
        if str(user.id) != str(card.assignee_id):
            return "❌ Вы не являетесь исполнителем"
        card.status = "in_progress"
        await db.commit()
        return "🚀 Задача переведена в работу"

    elif action == "task_complete":
        if str(user.id) != str(card.assignee_id):
            return "❌ Только исполнитель может завершить задачу"
        if can_transition(card.status, "in_review"):
            card.status = "in_review"
        elif can_transition(card.status, "done"):
            card.status = "done"
        else:
            return f"❌ Нельзя завершить задачу со статусом '{card.status}'"
        card.completed_at = now
        await db.commit()
        try:
            await notify_task_completed(db, card)
        except Exception:
            logger.exception("notify_task_completed failed for card %s", card.id)
        return "🏁 Задача отправлена на проверку"

    elif action == "task_approve":
        if str(user.id) not in [str(card.creator_id), str(card.reviewer_id)]:
            return "❌ Только постановщик может принять результат"
        card.status = "done"
        await db.commit()
        return "✔️ Задача принята и закрыта"

    elif action == "task_return":
        if str(user.id) not in [str(card.creator_id), str(card.reviewer_id)]:
            return "❌ Только постановщик может вернуть задачу"
        card.status = "in_progress"
        await db.commit()
        try:
            await notify_task_returned(db, card)
        except Exception:
            logger.exception("notify_task_returned failed for card %s", card.id)
        return "🔄 Задача возвращена в работу"

    return "❓ Неизвестное действие"


async def process_telegram_webhook(
    update: TelegramWebhookUpdate,
    db: AsyncSession,
) -> None:
    incoming = _extract_incoming_chat_and_text(update)
    if incoming is None:
        return

    chat_id, text = incoming
    stripped_text = text.strip()
    if not stripped_text:
        return

    # Handle task inline keyboard callbacks
    if stripped_text.startswith("task_"):
        try:
            response_text = await _handle_task_callback(db, stripped_text, chat_id)
        except Exception:
            logger.exception("_handle_task_callback failed for data=%s", stripped_text)
            response_text = "❌ Произошла ошибка при обработке команды"
        if response_text:
            await send_telegram_message(chat_id, response_text)
        return

    match = LINK_CODE_RE.match(stripped_text)
    if match:
        await _handle_link_command(chat_id, match.group(1), db)
        return

    command = parse_telegram_command_text(stripped_text)
    if command is None:
        return

    user = await _find_user_by_chat_id(chat_id, db)
    if user is None:
        await send_telegram_message(chat_id, LINK_REQUIRED_TEXT)
        return

    if command.name == "start":
        await send_telegram_message(
            chat_id,
            _build_help_text(user.name),
            reply_markup=_build_main_menu_markup(),
        )
        return

    response_text = await _handle_linked_command(command, user, db)
    if response_text:
        await send_telegram_message(chat_id, response_text)
