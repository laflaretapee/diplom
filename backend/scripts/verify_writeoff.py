"""
TASK-019 verification script: auto write-off of ingredients when creating an order.

Creates ingredient, StockItem with quantity=10, dish with tech-card,
creates order with that dish, waits 1 second, checks StockItem.quantity decreased.
"""
from __future__ import annotations

import asyncio
import sys
import uuid
from decimal import Decimal

sys.path.insert(0, "/workspace")

from sqlalchemy import select

# Import all models so SQLAlchemy mapper initializes correctly
import backend.app.models.franchisee  # noqa: F401
import backend.app.models.franchisee_task  # noqa: F401
import backend.app.models.user  # noqa: F401
import backend.app.models.user_point  # noqa: F401
from backend.app.db.session import SessionLocal
from backend.app.models.dish import Dish
from backend.app.models.dish_ingredient import DishIngredient
from backend.app.models.ingredient import Ingredient
from backend.app.models.order import PaymentType
from backend.app.models.point import Point
from backend.app.models.stock_item import StockItem
from backend.app.models.stock_movement import StockMovement


async def main() -> None:
    async with SessionLocal() as db:
        # Ensure we have at least one point
        point_result = await db.execute(select(Point).limit(1))
        point = point_result.scalar_one_or_none()
        if point is None:
            print("ERROR: No points found in DB. Run seed first.")
            sys.exit(1)

        point_id = point.id
        print(f"Using point: {point_id}")

        # Create ingredient
        ingredient = Ingredient(
            name=f"Test Ingredient {uuid.uuid4().hex[:6]}",
            unit="kg",
            min_stock_level=Decimal("0"),
        )
        db.add(ingredient)
        await db.flush()

        # Create StockItem with quantity=10
        stock_item = StockItem(
            ingredient_id=ingredient.id,
            point_id=point_id,
            quantity=Decimal("10"),
        )
        db.add(stock_item)
        await db.flush()

        # Create dish
        dish = Dish(
            name=f"Test Dish {uuid.uuid4().hex[:6]}",
            description="Test dish for write-off verification",
            price=Decimal("500"),
            is_active=True,
        )
        db.add(dish)
        await db.flush()

        # Create DishIngredient: 2 kg per portion
        quantity_per_portion = Decimal("2")
        di = DishIngredient(
            dish_id=dish.id,
            ingredient_id=ingredient.id,
            quantity_per_portion=quantity_per_portion,
        )
        db.add(di)
        await db.commit()

        stock_item_id = stock_item.id
        print(f"Created ingredient: {ingredient.id}, name: {ingredient.name}")
        print(f"Created StockItem: {stock_item_id}, initial quantity: 10")
        print(f"Created dish: {dish.id}, name: {dish.name}")
        print(f"DishIngredient: {quantity_per_portion} kg per portion")

        # Create order using the service (which triggers write-off)
        from backend.app.models.order import SourceChannel
        from backend.app.modules.orders.schemas import OrderCreate, OrderItem
        from backend.app.modules.orders.service import create_order

        order_data = OrderCreate(
            point_id=point_id,
            payment_type=PaymentType.CASH,
            source_channel=SourceChannel.POS,
            items=[
                OrderItem(
                    name=dish.name,
                    quantity=2,
                    price=Decimal("500"),
                )
            ],
        )
        order = await create_order(order_data, db)
        print(f"Created order: {order.id}")

    # Wait for async write-off to complete
    print("Waiting 2 seconds for write-off task to complete...")
    await asyncio.sleep(2)

    # Check result
    async with SessionLocal() as db:
        result = await db.execute(select(StockItem).where(StockItem.id == stock_item_id))
        updated_si = result.scalar_one_or_none()
        if updated_si is None:
            print("ERROR: StockItem not found after test!")
            sys.exit(1)

        expected = Decimal("10") - quantity_per_portion * 2  # 10 - 2*2 = 6
        actual = updated_si.quantity
        print(f"StockItem quantity: initial=10, expected={expected}, actual={actual}")

        # Check movements
        movements_result = await db.execute(
            select(StockMovement).where(StockMovement.stock_item_id == stock_item_id)
        )
        movements = movements_result.scalars().all()
        print(f"StockMovements created: {len(movements)}")
        for m in movements:
            print(f"  - type={m.movement_type}, qty={m.quantity}, reason={m.reason}")

        if actual == expected:
            print("\nSUCCESS: Ingredient write-off works correctly!")
        else:
            print(f"\nFAIL: Expected quantity {expected}, got {actual}")
            sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
