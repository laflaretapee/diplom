from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import date
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.ws_manager import ws_manager
from backend.app.models.order import Order, OrderStatus
from backend.app.models.point import Point
from backend.app.modules.orders.schemas import OrderCreate, OrderStatusUpdate

logger = logging.getLogger(__name__)

# Valid status transitions
VALID_TRANSITIONS: dict[OrderStatus, list[OrderStatus]] = {
    OrderStatus.NEW: [OrderStatus.IN_PROGRESS, OrderStatus.CANCELLED],
    OrderStatus.IN_PROGRESS: [OrderStatus.READY],
    OrderStatus.READY: [OrderStatus.DELIVERED],
    OrderStatus.DELIVERED: [],
    OrderStatus.CANCELLED: [],
}


async def write_off_for_order(
    order_id: uuid.UUID,
    point_id: uuid.UUID,
    items: list[dict],
) -> None:
    """Write off ingredients from stock for a given order (runs with its own DB session)."""
    from backend.app.db.session import SessionLocal
    from backend.app.models.dish import Dish
    from backend.app.models.dish_ingredient import DishIngredient
    from backend.app.models.stock_item import StockItem
    from backend.app.models.stock_movement import StockMovement, MovementType
    from backend.app.modules.warehouse.service import check_and_notify_low_stock

    async with SessionLocal() as db:
        try:
            low_stock_checks: list[tuple[uuid.UUID, Decimal]] = []
            for item in items:
                dish_id = item.get("dish_id")
                dish_name = item.get("name")
                item_quantity = Decimal(str(item.get("quantity", 1)))

                dish = None
                if dish_id:
                    dish_result = await db.execute(
                        select(Dish).where(Dish.id == dish_id, Dish.is_active == True)
                    )
                    dish = dish_result.scalar_one_or_none()

                if dish is None and dish_name:
                    dish_result = await db.execute(
                        select(Dish).where(Dish.name == dish_name, Dish.is_active == True)
                    )
                    dish = dish_result.scalar_one_or_none()
                if dish is None:
                    logger.debug(
                        "write_off_for_order: dish id='%s' name='%s' not found or inactive, skipping",
                        dish_id,
                        dish_name,
                    )
                    continue

                # Get all ingredients for this dish
                di_result = await db.execute(
                    select(DishIngredient).where(DishIngredient.dish_id == dish.id)
                )
                dish_ingredients = di_result.scalars().all()

                for dish_ingredient in dish_ingredients:
                    # Find StockItem for this ingredient at this point
                    si_result = await db.execute(
                        select(StockItem).where(
                            StockItem.ingredient_id == dish_ingredient.ingredient_id,
                            StockItem.point_id == point_id,
                        )
                    )
                    stock_item = si_result.scalar_one_or_none()
                    if stock_item is None:
                        logger.debug(
                            "write_off_for_order: StockItem not found for ingredient %s at point %s, skipping",
                            dish_ingredient.ingredient_id,
                            point_id,
                        )
                        continue

                    previous_quantity = stock_item.quantity
                    write_off_qty = dish_ingredient.quantity_per_portion * item_quantity
                    stock_item.quantity -= write_off_qty
                    low_stock_checks.append((stock_item.id, previous_quantity))

                    if stock_item.quantity < 0:
                        logger.warning(
                            "write_off_for_order: StockItem %s went below zero (quantity=%s) for order %s",
                            stock_item.id,
                            stock_item.quantity,
                            order_id,
                        )

                    movement = StockMovement(
                        stock_item_id=stock_item.id,
                        movement_type=MovementType.OUT,
                        quantity=write_off_qty,
                        reason=f"order:{order_id}",
                        created_by_id=None,
                    )
                    db.add(movement)

            await db.commit()
            for stock_item_id, previous_quantity in low_stock_checks:
                await check_and_notify_low_stock(stock_item_id, previous_quantity)
            logger.info("write_off_for_order: completed write-off for order %s", order_id)
        except Exception as exc:
            logger.exception(
                "write_off_for_order: failed for order %s: %s", order_id, exc
            )


async def create_order(
    data: OrderCreate,
    db: AsyncSession,
) -> Order:
    # Validate payment_type against point.payment_types
    point_result = await db.execute(select(Point).where(Point.id == data.point_id))
    point = point_result.scalar_one_or_none()
    if point is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Point not found")
    if point.payment_types:  # non-empty list means restriction is enforced
        if data.payment_type.value not in point.payment_types:
            raise HTTPException(
                status_code=422,
                detail=f"Payment type '{data.payment_type}' is not allowed for this point. "
                       f"Allowed: {point.payment_types}",
            )

    total = Decimal("0")
    for item in data.items:
        total += item.price * item.quantity

    order = Order(
        point_id=data.point_id,
        payment_type=data.payment_type,
        source_channel=data.source_channel,
        items=[item.model_dump(mode="json") for item in data.items],
        total_amount=total,
        notes=data.notes,
    )
    db.add(order)
    await db.commit()
    await db.refresh(order)

    # Async write-off of ingredients (non-blocking, uses its own session)
    asyncio.create_task(
        write_off_for_order(order.id, order.point_id, order.items)
    )

    # Async fire-and-forget для уведомления
    from backend.app.tasks.notifications import send_order_notification
    send_order_notification.delay(
        order_id=str(order.id),
        point_id=str(order.point_id),
        event_type="order_created",
        recipients=[],  # будет заполнено когда реализуем Telegram
        total_amount=str(order.total_amount),
        status=order.status.value,
    )

    asyncio.create_task(ws_manager.broadcast(str(order.point_id), {
        "type": "order_created",
        "order_id": str(order.id),
        "status": order.status.value,
        "total_amount": str(order.total_amount),
    }))
    return order


async def list_orders(
    point_id: uuid.UUID,
    db: AsyncSession,
    status: OrderStatus | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
) -> list[Order]:
    q = select(Order).where(Order.point_id == point_id)
    if status is not None:
        q = q.where(Order.status == status)
    if date_from is not None:
        q = q.where(Order.created_at >= date_from)
    if date_to is not None:
        from datetime import timedelta
        q = q.where(Order.created_at < date_to + timedelta(days=1))
    q = q.order_by(Order.created_at.desc())
    result = await db.execute(q)
    return list(result.scalars().all())


async def get_order(order_id: uuid.UUID, db: AsyncSession) -> Order:
    result = await db.execute(select(Order).where(Order.id == order_id))
    order = result.scalar_one_or_none()
    if order is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
    return order


async def update_order_status(
    order_id: uuid.UUID,
    data: OrderStatusUpdate,
    db: AsyncSession,
) -> Order:
    order = await get_order(order_id, db)
    allowed = VALID_TRANSITIONS.get(order.status, [])
    if data.status not in allowed:
        raise HTTPException(
            status_code=422,
            detail=f"Cannot transition from {order.status} to {data.status}",
        )
    order.status = data.status
    await db.commit()
    await db.refresh(order)
    if data.status == OrderStatus.CANCELLED:
        from backend.app.tasks.notifications import send_order_notification

        send_order_notification.delay(
            order_id=str(order.id),
            point_id=str(order.point_id),
            event_type="order_cancelled",
            recipients=[],
            total_amount=str(order.total_amount),
            status=order.status.value,
        )
    asyncio.create_task(ws_manager.broadcast(str(order.point_id), {
        "type": "order_status_changed",
        "order_id": str(order.id),
        "status": order.status.value,
        "total_amount": str(order.total_amount),
    }))
    return order
