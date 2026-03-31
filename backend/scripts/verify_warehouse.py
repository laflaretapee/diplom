"""
Verify warehouse models: Ingredient, StockItem, StockMovement.
Steps:
1. Create ingredient "Rice", unit="kg", min_stock=5
2. Create StockItem for Rice on an existing point
3. Record a movement "in" qty=10
4. Verify that quantity != 0 (movement is recorded)
5. Try to create duplicate StockItem for same point+ingredient -> IntegrityError
"""
import asyncio
import sys

sys.path.insert(0, "/workspace")

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from backend.app.db.session import SessionLocal
from backend.app.models.ingredient import Ingredient
from backend.app.models.point import Point
from backend.app.models.stock_item import StockItem
from backend.app.models.stock_movement import MovementType, StockMovement


async def main() -> None:
    async with SessionLocal() as db:
        # Find an existing point
        result = await db.execute(select(Point).limit(1))
        point = result.scalar_one_or_none()
        if point is None:
            print("FAIL: No points found in DB. Run verify_rbac.py first.")
            sys.exit(1)
        print(f"Using point: {point.name} ({point.id})")

        # Cleanup: remove existing "Rice" ingredient if any
        existing_ing = await db.execute(select(Ingredient).where(Ingredient.name == "Rice"))
        existing_ing = existing_ing.scalar_one_or_none()
        if existing_ing:
            # Remove related stock items/movements first
            existing_si = await db.execute(
                select(StockItem).where(StockItem.ingredient_id == existing_ing.id)
            )
            for si in existing_si.scalars().all():
                await db.delete(si)
            await db.delete(existing_ing)
            await db.flush()

        # Step 1: Create ingredient "Rice"
        ingredient = Ingredient(
            name="Rice",
            unit="kg",
            min_stock_level=Decimal("5"),
            is_active=True,
        )
        db.add(ingredient)
        await db.flush()
        await db.refresh(ingredient)
        print(f"PASS step 1: Ingredient created: {ingredient.name} ({ingredient.id})")

        # Step 2: Create StockItem for Rice on the point
        stock_item = StockItem(
            ingredient_id=ingredient.id,
            point_id=point.id,
            quantity=Decimal("0"),
        )
        db.add(stock_item)
        await db.flush()
        await db.refresh(stock_item)
        print(f"PASS step 2: StockItem created: {stock_item.id}")

        # Step 3: Record movement "in" qty=10
        movement = StockMovement(
            stock_item_id=stock_item.id,
            movement_type=MovementType.IN,
            quantity=Decimal("10"),
            reason="Initial stock",
        )
        db.add(movement)
        await db.commit()
        await db.refresh(movement)
        print(f"PASS step 3: StockMovement recorded: type={movement.movement_type}, qty={movement.quantity}")

        # Step 4: Verify movement quantity is not 0 (movement was recorded)
        mov_check = await db.execute(
            select(StockMovement).where(StockMovement.stock_item_id == stock_item.id)
        )
        movements = mov_check.scalars().all()
        assert len(movements) > 0 and movements[0].quantity != Decimal("0"), \
            "FAIL step 4: Movement quantity is 0 or no movements found"
        print(f"PASS step 4: Movement exists with qty={movements[0].quantity} (not 0)")

        # Step 5: Try to create duplicate StockItem -> IntegrityError
        try:
            duplicate = StockItem(
                ingredient_id=ingredient.id,
                point_id=point.id,
                quantity=Decimal("5"),
            )
            db.add(duplicate)
            await db.flush()
            print("FAIL step 5: Should have raised IntegrityError for duplicate StockItem")
        except IntegrityError:
            await db.rollback()
            print("PASS step 5: IntegrityError raised for duplicate StockItem (as expected)")

        print("\nAll warehouse checks done.")


asyncio.run(main())
