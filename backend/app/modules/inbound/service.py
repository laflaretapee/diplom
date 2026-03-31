from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.dish import Dish
from backend.app.models.order import SourceChannel
from backend.app.models.order import Order
from backend.app.models.point import Point
from backend.app.modules.inbound.schemas import InboundOrderRequest
from backend.app.modules.orders.schemas import OrderCreate, OrderItem


async def _resolve_inbound_dish(item, db: AsyncSession) -> Dish:
    if item.dish_id is not None:
        dish_result = await db.execute(
            select(Dish).where(Dish.id == item.dish_id, Dish.is_active.is_(True))
        )
        dish = dish_result.scalar_one_or_none()
        if dish is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "code": "dish_not_found",
                    "message": "Dish was not found for inbound validation",
                    "dish_id": str(item.dish_id),
                    "dish_name": item.name,
                },
            )
        if item.name != dish.name:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "code": "dish_identity_mismatch",
                    "message": "dish_id and name refer to different dishes",
                    "dish_id": str(dish.id),
                    "dish_name": dish.name,
                    "provided_name": item.name,
                },
            )
        return dish

    dish_result = await db.execute(
        select(Dish).where(Dish.name == item.name, Dish.is_active.is_(True))
    )
    dish = dish_result.scalar_one_or_none()
    if dish is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "code": "dish_not_found",
                "message": "Dish was not found for inbound validation",
                "dish_name": item.name,
            },
        )
    return dish


async def _validate_inbound_dish_channels(
    data: InboundOrderRequest,
    db: AsyncSession,
) -> list[OrderItem]:
    source_channel = data.source_channel.value
    normalized_items: list[OrderItem] = []
    for item in data.items:
        dish = await _resolve_inbound_dish(item, db)
        if source_channel in dish.available_channels:
            normalized_items.append(
                OrderItem(
                    dish_id=dish.id,
                    name=dish.name,
                    quantity=item.quantity,
                    price=item.price,
                )
            )
            continue
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "code": "dish_channel_unavailable",
                "message": f"Dish '{dish.name}' is disabled for source channel '{source_channel}'",
                "dish_id": str(dish.id),
                "dish_name": dish.name,
                "source_channel": source_channel,
                "available_channels": dish.available_channels,
            },
        )
    return normalized_items


async def create_inbound_order(
    data: InboundOrderRequest,
    db: AsyncSession,
) -> Order:
    # Check point exists and is active
    result = await db.execute(select(Point).where(Point.id == data.point_id))
    point = result.scalar_one_or_none()
    if point is None or not point.is_active:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Point not found or inactive",
        )

    normalized_items = await _validate_inbound_dish_channels(data, db)

    # Reuse orders service create_order by building an OrderCreate schema
    order_create = OrderCreate(
        point_id=data.point_id,
        payment_type=data.payment_type,
        source_channel=SourceChannel(data.source_channel.value),
        items=normalized_items,
        notes=data.notes,
    )

    from backend.app.modules.orders import service as orders_service
    return await orders_service.create_order(order_create, db)
