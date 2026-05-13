"""
Create a real low-stock threshold crossing without monkeypatching notifications.
"""
from __future__ import annotations

import asyncio
import sys
import uuid
from decimal import Decimal

sys.path.insert(0, "/workspace")

from sqlalchemy import select

import backend.app.models.franchisee  # noqa: F401
import backend.app.models.franchisee_task  # noqa: F401
import backend.app.models.user  # noqa: F401
import backend.app.models.user_point  # noqa: F401
from backend.app.db.session import SessionLocal
from backend.app.models.ingredient import Ingredient
from backend.app.models.point import Point
from backend.app.models.stock_item import StockItem
from backend.app.models.user import User
from backend.app.modules.warehouse.schemas import MovementCreate
from backend.app.modules.warehouse.service import create_movement


async def main() -> None:
    async with SessionLocal() as db:
        point = (await db.execute(select(Point).limit(1))).scalar_one()
        user = (await db.execute(select(User).limit(1))).scalar_one()

        ingredient = Ingredient(
            name=f"Live Low Stock {uuid.uuid4().hex[:6]}",
            unit="kg",
            min_stock_level=Decimal("5"),
        )
        db.add(ingredient)
        await db.flush()

        stock_item = StockItem(
            ingredient_id=ingredient.id,
            point_id=point.id,
            quantity=Decimal("10"),
        )
        db.add(stock_item)
        await db.commit()

        await create_movement(
            MovementCreate(
                stock_item_id=stock_item.id,
                movement_type="out",
                quantity=Decimal("6"),
                reason="live-low-stock",
            ),
            user.id,
            db,
        )
        print(
            "Triggered live low_stock for "
            f"ingredient={ingredient.id} stock_item={stock_item.id} point={point.id}"
        )


if __name__ == "__main__":
    asyncio.run(main())
