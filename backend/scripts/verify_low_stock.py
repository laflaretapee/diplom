"""
TASK-022 verification: low_stock notification fires once on threshold crossing.

This script verifies two paths:
1. Manual stock movements ("out") only notify when quantity crosses below min_stock_level.
2. Automatic order write-off also emits low_stock when it crosses the threshold.
"""
from __future__ import annotations

import asyncio
import sys
import uuid
from decimal import Decimal
from unittest.mock import patch

sys.path.insert(0, "/workspace")

import backend.app.models.franchisee  # noqa: F401
import backend.app.models.franchisee_task  # noqa: F401
import backend.app.models.user  # noqa: F401
import backend.app.models.user_point  # noqa: F401
from sqlalchemy import select

from backend.app.db.session import SessionLocal
from backend.app.models.dish import Dish
from backend.app.models.dish_ingredient import DishIngredient
from backend.app.models.ingredient import Ingredient
from backend.app.models.point import Point
from backend.app.models.stock_item import StockItem
from backend.app.models.user import User
from backend.app.modules.orders.schemas import OrderCreate, OrderItem
from backend.app.modules.orders.service import create_order
from backend.app.modules.warehouse.schemas import MovementCreate
from backend.app.modules.warehouse.service import create_movement


async def build_fixture(
    db,
    *,
    suffix: str,
    quantity: Decimal,
    min_stock_level: Decimal,
) -> tuple[uuid.UUID, uuid.UUID, uuid.UUID]:
    point = (await db.execute(select(Point).limit(1))).scalar_one_or_none()
    user = (await db.execute(select(User).limit(1))).scalar_one_or_none()
    if point is None or user is None:
        print("ERROR: expected at least one point and one user in DB")
        sys.exit(1)

    ingredient = Ingredient(
        name=f"Low Stock Ingredient {suffix}",
        unit="kg",
        min_stock_level=min_stock_level,
    )
    db.add(ingredient)
    await db.flush()

    stock_item = StockItem(
        ingredient_id=ingredient.id,
        point_id=point.id,
        quantity=quantity,
    )
    db.add(stock_item)
    await db.flush()
    await db.commit()
    return point.id, user.id, stock_item.id


async def verify_manual_movement_path(calls: list[dict]) -> None:
    async with SessionLocal() as db:
        point_id, user_id, stock_item_id = await build_fixture(
            db,
            suffix=f"manual-{uuid.uuid4().hex[:6]}",
            quantity=Decimal("10"),
            min_stock_level=Decimal("5"),
        )
        print(f"Manual path fixture: point={point_id} stock_item={stock_item_id}")

        await create_movement(
            MovementCreate(
                stock_item_id=stock_item_id,
                movement_type="out",
                quantity=Decimal("4"),
                reason="manual-test-above-min",
            ),
            created_by_id=user_id,
            db=db,
        )
        await asyncio.sleep(0.3)
        if len(calls) != 0:
            raise AssertionError(f"Expected 0 notifications above threshold, got {len(calls)}")

        await create_movement(
            MovementCreate(
                stock_item_id=stock_item_id,
                movement_type="out",
                quantity=Decimal("2"),
                reason="manual-test-cross-threshold",
            ),
            created_by_id=user_id,
            db=db,
        )
        await asyncio.sleep(0.5)
        if len(calls) != 1:
            raise AssertionError(
                f"Expected 1 notification after threshold crossing, got {len(calls)}"
            )

        await create_movement(
            MovementCreate(
                stock_item_id=stock_item_id,
                movement_type="out",
                quantity=Decimal("1"),
                reason="manual-test-still-below",
            ),
            created_by_id=user_id,
            db=db,
        )
        await asyncio.sleep(0.5)
        if len(calls) != 1:
            raise AssertionError(
                "Expected no duplicate notification while still below threshold"
            )


async def verify_order_writeoff_path(calls: list[dict]) -> None:
    async with SessionLocal() as db:
        point_id, _, stock_item_id = await build_fixture(
            db,
            suffix=f"order-{uuid.uuid4().hex[:6]}",
            quantity=Decimal("10"),
            min_stock_level=Decimal("5"),
        )

        ingredient_id = (
            await db.execute(select(StockItem.ingredient_id).where(StockItem.id == stock_item_id))
        ).scalar_one()

        dish = Dish(
            name=f"Low Stock Dish {uuid.uuid4().hex[:6]}",
            description="Triggers low-stock via order write-off",
            price=Decimal("500"),
            is_active=True,
        )
        db.add(dish)
        await db.flush()

        db.add(
            DishIngredient(
                dish_id=dish.id,
                ingredient_id=ingredient_id,
                quantity_per_portion=Decimal("8"),
            )
        )
        await db.commit()

        baseline_calls = len(calls)
        await create_order(
            OrderCreate(
                point_id=point_id,
                payment_type="cash",
                source_channel="pos",
                items=[OrderItem(name=dish.name, quantity=1, price=Decimal("500"))],
            ),
            db=db,
        )

    await asyncio.sleep(2)
    if len(calls) != baseline_calls + 1:
        raise AssertionError(
            "Expected order write-off to enqueue one low-stock notification"
        )


async def main() -> None:
    calls: list[dict] = []

    def fake_delay(*args, **kwargs):
        calls.append(kwargs)
        return None

    with patch("backend.app.tasks.notifications.send_low_stock_notification.delay", fake_delay):
        await verify_manual_movement_path(calls)
        await verify_order_writeoff_path(calls)

    print("SUCCESS: low_stock notifications fire only on threshold crossing.")
    for index, payload in enumerate(calls, start=1):
        print(f"  call {index}: {payload}")


if __name__ == "__main__":
    asyncio.run(main())
