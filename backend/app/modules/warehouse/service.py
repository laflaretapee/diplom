from __future__ import annotations

import uuid
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.ingredient import Ingredient
from backend.app.models.stock_item import StockItem
from backend.app.models.stock_movement import MovementType, StockMovement
from backend.app.modules.warehouse.schemas import (
    DishCreate,
    DishUpdate,
    IngredientCreate,
    IngredientUpdate,
    MovementCreate,
    StockItemResponse,
)

# ── Ingredients ───────────────────────────────────────────────────────────────

async def create_ingredient(data: IngredientCreate, db: AsyncSession) -> Ingredient:
    ingredient = Ingredient(
        name=data.name,
        unit=data.unit,
        min_stock_level=data.min_stock_level,
    )
    db.add(ingredient)
    await db.commit()
    await db.refresh(ingredient)
    return ingredient


async def list_ingredients(db: AsyncSession, is_active: bool = True) -> list[Ingredient]:
    result = await db.execute(
        select(Ingredient).where(Ingredient.is_active == is_active).order_by(Ingredient.name)
    )
    return list(result.scalars().all())


async def get_ingredient(ingredient_id: uuid.UUID, db: AsyncSession) -> Ingredient:
    result = await db.execute(select(Ingredient).where(Ingredient.id == ingredient_id))
    ingredient = result.scalar_one_or_none()
    if ingredient is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ingredient not found")
    return ingredient


async def update_ingredient(
    ingredient_id: uuid.UUID, data: IngredientUpdate, db: AsyncSession
) -> Ingredient:
    ingredient = await get_ingredient(ingredient_id, db)
    if data.name is not None:
        ingredient.name = data.name
    if data.min_stock_level is not None:
        ingredient.min_stock_level = data.min_stock_level
    if data.is_active is not None:
        ingredient.is_active = data.is_active
    await db.commit()
    await db.refresh(ingredient)
    return ingredient


# ── Stock ─────────────────────────────────────────────────────────────────────

async def get_stock_for_point(
    point_id: uuid.UUID, db: AsyncSession
) -> list[StockItemResponse]:
    result = await db.execute(
        select(StockItem, Ingredient)
        .join(Ingredient, StockItem.ingredient_id == Ingredient.id)
        .where(StockItem.point_id == point_id)
        .order_by(Ingredient.name)
    )
    rows = result.all()
    items = []
    for stock_item, ingredient in rows:
        items.append(
            StockItemResponse(
                stock_item_id=stock_item.id,
                ingredient_id=ingredient.id,
                ingredient_name=ingredient.name,
                unit=ingredient.unit,
                quantity=stock_item.quantity,
                min_stock_level=ingredient.min_stock_level,
                is_below_minimum=stock_item.quantity < ingredient.min_stock_level,
            )
        )
    return items


async def create_movement(
    data: MovementCreate,
    created_by_id: uuid.UUID,
    db: AsyncSession,
) -> StockMovement:
    # Fetch the stock item inside the selected point to keep tenant scope explicit.
    result = await db.execute(
        select(StockItem).where(
            StockItem.id == data.stock_item_id,
            StockItem.point_id == data.point_id,
        )
    )
    stock_item = result.scalar_one_or_none()
    if stock_item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="StockItem not found")

    movement_type = data.movement_type
    previous_quantity = stock_item.quantity
    if movement_type == MovementType.IN.value:
        if data.quantity <= 0:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Quantity must be greater than 0 for incoming stock",
            )
        stock_item.quantity = stock_item.quantity + data.quantity
    elif movement_type == MovementType.OUT.value:
        if data.quantity <= 0:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Quantity must be greater than 0 for outgoing stock",
            )
        if stock_item.quantity < data.quantity:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Insufficient stock quantity",
            )
        stock_item.quantity = stock_item.quantity - data.quantity
    elif movement_type == MovementType.ADJUSTMENT.value:
        stock_item.quantity = data.quantity
    else:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid movement_type. Use: in, out, adjustment",
        )

    movement = StockMovement(
        stock_item_id=data.stock_item_id,
        movement_type=MovementType(movement_type),
        quantity=data.quantity,
        reason=data.reason,
        created_by_id=created_by_id,
    )
    db.add(movement)
    await db.commit()
    await db.refresh(movement)

    if movement_type in (MovementType.OUT.value, MovementType.ADJUSTMENT.value):
        import asyncio

        asyncio.create_task(check_and_notify_low_stock(stock_item.id, previous_quantity))

    return movement


# ── Supply (incoming stock) ───────────────────────────────────────────────────

async def create_supply(
    data,
    created_by_id: uuid.UUID,
    db: AsyncSession,
):
    """Find or create StockItem, add quantity, create 'in' movement."""
    from backend.app.modules.warehouse.schemas import SupplyResponse

    # Verify ingredient exists
    await get_ingredient(data.ingredient_id, db)

    # Find or create StockItem
    si_result = await db.execute(
        select(StockItem).where(
            StockItem.ingredient_id == data.ingredient_id,
            StockItem.point_id == data.point_id,
        )
    )
    stock_item = si_result.scalar_one_or_none()
    if stock_item is None:
        stock_item = StockItem(
            ingredient_id=data.ingredient_id,
            point_id=data.point_id,
            quantity=Decimal("0"),
        )
        db.add(stock_item)
        await db.flush()

    stock_item.quantity += data.quantity

    supplier = data.supplier_name.strip() if data.supplier_name else None
    reason_parts = [f"Поставка от {supplier}" if supplier else "Поставка"]
    if data.note:
        reason_parts.append(data.note)
    reason = "; ".join(reason_parts)
    # Truncate to 255 chars (reason field limit)
    reason = reason[:255]

    movement = StockMovement(
        stock_item_id=stock_item.id,
        movement_type=MovementType.IN,
        quantity=data.quantity,
        reason=reason,
        created_by_id=created_by_id,
    )
    db.add(movement)
    await db.commit()
    await db.refresh(stock_item)
    await db.refresh(movement)

    return SupplyResponse(
        stock_item_id=stock_item.id,
        ingredient_id=stock_item.ingredient_id,
        new_quantity=stock_item.quantity,
        movement_id=movement.id,
    )


async def list_movements(
    point_id: uuid.UUID,
    db: AsyncSession,
    ingredient_id: uuid.UUID | None = None,
    movement_type: str | None = None,
    limit: int = 50,
):
    """Return movement history for a given point with ingredient names and user info."""
    from backend.app.models.user import User
    from backend.app.modules.warehouse.schemas import MovementHistoryItem

    q = (
        select(StockMovement, StockItem, Ingredient, User)
        .join(StockItem, StockMovement.stock_item_id == StockItem.id)
        .join(Ingredient, StockItem.ingredient_id == Ingredient.id)
        .outerjoin(User, StockMovement.created_by_id == User.id)
        .where(StockItem.point_id == point_id)
    )
    if ingredient_id is not None:
        q = q.where(StockItem.ingredient_id == ingredient_id)
    if movement_type is not None:
        q = q.where(StockMovement.movement_type == movement_type)
    q = q.order_by(StockMovement.created_at.desc()).limit(limit)

    result = await db.execute(q)
    rows = result.all()

    return [
        MovementHistoryItem(
            id=movement.id,
            stock_item_id=movement.stock_item_id,
            ingredient_id=ingredient.id,
            ingredient_name=ingredient.name,
            movement_type=(
                movement.movement_type.value
                if hasattr(movement.movement_type, "value")
                else movement.movement_type
            ),
            quantity=movement.quantity,
            reason=movement.reason,
            created_at=movement.created_at.isoformat(),
            created_by_id=str(movement.created_by_id) if movement.created_by_id else None,
            created_by_name=user.name if user else None,
        )
        for movement, stock_item, ingredient, user in rows
    ]


async def list_audit(
    point_id: uuid.UUID,
    db: AsyncSession,
    date_from=None,
    date_to=None,
    limit: int = 100,
):
    """Return full audit log for a given point, sorted by created_at DESC."""
    from datetime import timedelta

    from backend.app.models.user import User
    from backend.app.modules.warehouse.schemas import MovementHistoryItem

    q = (
        select(StockMovement, StockItem, Ingredient, User)
        .join(StockItem, StockMovement.stock_item_id == StockItem.id)
        .join(Ingredient, StockItem.ingredient_id == Ingredient.id)
        .outerjoin(User, StockMovement.created_by_id == User.id)
        .where(StockItem.point_id == point_id)
    )
    if date_from is not None:
        q = q.where(StockMovement.created_at >= date_from)
    if date_to is not None:
        q = q.where(StockMovement.created_at < date_to + timedelta(days=1))
    q = q.order_by(StockMovement.created_at.desc()).limit(limit)

    result = await db.execute(q)
    rows = result.all()

    return [
        MovementHistoryItem(
            id=movement.id,
            stock_item_id=movement.stock_item_id,
            ingredient_id=ingredient.id,
            ingredient_name=ingredient.name,
            movement_type=(
                movement.movement_type.value
                if hasattr(movement.movement_type, "value")
                else movement.movement_type
            ),
            quantity=movement.quantity,
            reason=movement.reason,
            created_at=movement.created_at.isoformat(),
            created_by_id=str(movement.created_by_id) if movement.created_by_id else None,
            created_by_name=user.name if user else None,
        )
        for movement, stock_item, ingredient, user in rows
    ]


# ── Low Stock Notification ────────────────────────────────────────────────────

async def check_and_notify_low_stock(
    stock_item_id: uuid.UUID,
    previous_quantity: Decimal | None = None,
) -> None:
    """Send low_stock only when quantity crosses from at/above minimum to below minimum."""
    from backend.app.db.session import SessionLocal
    from backend.app.tasks.notifications import send_low_stock_notification

    async with SessionLocal() as db:
        result = await db.execute(
            select(StockItem).where(StockItem.id == stock_item_id)
        )
        item = result.scalar_one_or_none()
        if not item:
            return
        ing_result = await db.execute(
            select(Ingredient).where(Ingredient.id == item.ingredient_id)
        )
        ing = ing_result.scalar_one_or_none()
        if not ing:
            return
        if item.quantity >= ing.min_stock_level:
            return
        if previous_quantity is not None and previous_quantity < ing.min_stock_level:
            return
        if item.quantity < ing.min_stock_level:
            send_low_stock_notification.delay(
                ingredient_id=str(ing.id),
                point_id=str(item.point_id),
                current_qty=float(item.quantity),
                min_qty=float(ing.min_stock_level),
            )


# ── Dishes ────────────────────────────────────────────────────────────────────

async def create_dish(data: DishCreate, db: AsyncSession):
    from backend.app.models.dish import Dish, normalize_dish_sales_channels
    dish = Dish(
        name=data.name,
        description=data.description,
        price=data.price,
        available_channels=normalize_dish_sales_channels(data.available_channels),
    )
    db.add(dish)
    await db.commit()
    await db.refresh(dish)
    return dish


async def list_dishes(db: AsyncSession, is_active: bool = True):
    from backend.app.models.dish import Dish
    result = await db.execute(
        select(Dish).where(Dish.is_active == is_active).order_by(Dish.name)
    )
    return list(result.scalars().all())


async def get_dish(dish_id: uuid.UUID, db: AsyncSession):
    from backend.app.models.dish import Dish
    result = await db.execute(select(Dish).where(Dish.id == dish_id))
    dish = result.scalar_one_or_none()
    if dish is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dish not found")
    return dish


async def update_dish(
    dish_id: uuid.UUID,
    data: DishUpdate,
    db: AsyncSession,
):
    from backend.app.models.dish import normalize_dish_sales_channels

    dish = await get_dish(dish_id, db)
    if data.name is not None:
        dish.name = data.name
    if data.description is not None:
        dish.description = data.description
    if data.price is not None:
        dish.price = data.price
    if data.is_active is not None:
        dish.is_active = data.is_active
    if data.available_channels is not None:
        dish.available_channels = normalize_dish_sales_channels(data.available_channels)
    await db.commit()
    await db.refresh(dish)
    return dish


async def add_dish_ingredient(dish_id: uuid.UUID, data, db: AsyncSession):
    from backend.app.models.dish_ingredient import DishIngredient
    # Verify dish exists
    await get_dish(dish_id, db)
    # Verify ingredient exists
    await get_ingredient(data.ingredient_id, db)

    # Check for duplicate
    result = await db.execute(
        select(DishIngredient).where(
            DishIngredient.dish_id == dish_id,
            DishIngredient.ingredient_id == data.ingredient_id,
        )
    )
    existing = result.scalar_one_or_none()
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ingredient already in dish recipe",
        )

    di = DishIngredient(
        dish_id=dish_id,
        ingredient_id=data.ingredient_id,
        quantity_per_portion=data.quantity_per_portion,
    )
    db.add(di)
    await db.commit()
    await db.refresh(di)
    return di


async def list_dish_ingredients(dish_id: uuid.UUID, db: AsyncSession):
    from backend.app.models.dish_ingredient import DishIngredient
    await get_dish(dish_id, db)
    result = await db.execute(
        select(DishIngredient, Ingredient)
        .join(Ingredient, DishIngredient.ingredient_id == Ingredient.id)
        .where(DishIngredient.dish_id == dish_id)
        .order_by(Ingredient.name)
    )
    rows = result.all()
    return [
        {
            "id": di.id,
            "dish_id": di.dish_id,
            "ingredient_id": ingredient.id,
            "ingredient_name": ingredient.name,
            "unit": ingredient.unit,
            "quantity_per_portion": di.quantity_per_portion,
        }
        for di, ingredient in rows
    ]


async def delete_dish_ingredient(
    dish_id: uuid.UUID, ingredient_id: uuid.UUID, db: AsyncSession
) -> None:
    from backend.app.models.dish_ingredient import DishIngredient
    result = await db.execute(
        select(DishIngredient).where(
            DishIngredient.dish_id == dish_id,
            DishIngredient.ingredient_id == ingredient_id,
        )
    )
    di = result.scalar_one_or_none()
    if di is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Ingredient not found in dish recipe",
        )
    await db.delete(di)
    await db.commit()
