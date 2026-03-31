from __future__ import annotations

import uuid
from datetime import date

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.deps import (
    require_any_role,
    require_manager_or_above,
    require_super_admin,
    verify_point_access,
)
from backend.app.db.session import get_db_session
from backend.app.models.user import User
from backend.app.modules.warehouse import service
from backend.app.modules.warehouse.schemas import (
    DishCreate,
    DishIngredientCreate,
    DishIngredientResponse,
    DishResponse,
    DishUpdate,
    IngredientCreate,
    IngredientResponse,
    IngredientUpdate,
    MovementCreate,
    MovementHistoryItem,
    MovementResponse,
    StockItemResponse,
    SupplyCreate,
    SupplyResponse,
)

router = APIRouter(prefix="/warehouse", tags=["warehouse"])


# ── Ingredients ───────────────────────────────────────────────────────────────

@router.post(
    "/ingredients",
    response_model=IngredientResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_ingredient(
    data: IngredientCreate,
    user: User = Depends(require_super_admin),
    db: AsyncSession = Depends(get_db_session),
) -> IngredientResponse:
    ingredient = await service.create_ingredient(data, db)
    return IngredientResponse.model_validate(ingredient)


@router.get("/ingredients", response_model=list[IngredientResponse])
async def list_ingredients(
    is_active: bool = True,
    user: User = Depends(require_manager_or_above),
    db: AsyncSession = Depends(get_db_session),
) -> list[IngredientResponse]:
    ingredients = await service.list_ingredients(db, is_active)
    return [IngredientResponse.model_validate(i) for i in ingredients]


@router.get("/ingredients/{ingredient_id}", response_model=IngredientResponse)
async def get_ingredient(
    ingredient_id: uuid.UUID,
    user: User = Depends(require_manager_or_above),
    db: AsyncSession = Depends(get_db_session),
) -> IngredientResponse:
    ingredient = await service.get_ingredient(ingredient_id, db)
    return IngredientResponse.model_validate(ingredient)


@router.patch("/ingredients/{ingredient_id}", response_model=IngredientResponse)
async def update_ingredient(
    ingredient_id: uuid.UUID,
    data: IngredientUpdate,
    user: User = Depends(require_super_admin),
    db: AsyncSession = Depends(get_db_session),
) -> IngredientResponse:
    ingredient = await service.update_ingredient(ingredient_id, data, db)
    return IngredientResponse.model_validate(ingredient)


# ── Stock ─────────────────────────────────────────────────────────────────────

@router.get("/stock", response_model=list[StockItemResponse])
async def get_stock(
    point_id: uuid.UUID,
    user: User = Depends(require_manager_or_above),
    db: AsyncSession = Depends(get_db_session),
) -> list[StockItemResponse]:
    await verify_point_access(point_id, user, db)
    return await service.get_stock_for_point(point_id, db)


@router.post(
    "/stock/movements",
    response_model=MovementResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_movement(
    data: MovementCreate,
    user: User = Depends(require_manager_or_above),
    db: AsyncSession = Depends(get_db_session),
) -> MovementResponse:
    await verify_point_access(data.point_id, user, db)
    movement = await service.create_movement(data, user.id, db)
    return MovementResponse.model_validate(movement)


# ── Supply & Movement History ─────────────────────────────────────────────────

@router.post(
    "/stock/supply",
    response_model=SupplyResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_supply(
    data: SupplyCreate,
    user: User = Depends(require_manager_or_above),
    db: AsyncSession = Depends(get_db_session),
) -> SupplyResponse:
    await verify_point_access(data.point_id, user, db)
    return await service.create_supply(data, user.id, db)


@router.get("/stock/movements", response_model=list[MovementHistoryItem])
async def list_movements(
    point_id: uuid.UUID,
    ingredient_id: uuid.UUID | None = None,
    movement_type: str | None = None,
    limit: int = 50,
    user: User = Depends(require_manager_or_above),
    db: AsyncSession = Depends(get_db_session),
) -> list[MovementHistoryItem]:
    await verify_point_access(point_id, user, db)
    return await service.list_movements(
        point_id=point_id,
        db=db,
        ingredient_id=ingredient_id,
        movement_type=movement_type,
        limit=limit,
    )


@router.get("/audit", response_model=list[MovementHistoryItem])
async def audit_log(
    point_id: uuid.UUID,
    date_from: date | None = None,
    date_to: date | None = None,
    limit: int = 100,
    user: User = Depends(require_manager_or_above),
    db: AsyncSession = Depends(get_db_session),
) -> list[MovementHistoryItem]:
    await verify_point_access(point_id, user, db)
    return await service.list_audit(
        point_id=point_id,
        db=db,
        date_from=date_from,
        date_to=date_to,
        limit=limit,
    )


# ── Dishes ────────────────────────────────────────────────────────────────────

@router.post("/dishes", response_model=DishResponse, status_code=status.HTTP_201_CREATED)
async def create_dish(
    data: DishCreate,
    user: User = Depends(require_super_admin),
    db: AsyncSession = Depends(get_db_session),
) -> DishResponse:
    dish = await service.create_dish(data, db)
    return DishResponse.model_validate(dish)


@router.get("/dishes", response_model=list[DishResponse])
async def list_dishes(
    is_active: bool = True,
    user: User = Depends(require_any_role),
    db: AsyncSession = Depends(get_db_session),
) -> list[DishResponse]:
    dishes = await service.list_dishes(db, is_active)
    return [DishResponse.model_validate(d) for d in dishes]


@router.patch("/dishes/{dish_id}", response_model=DishResponse)
async def update_dish(
    dish_id: uuid.UUID,
    data: DishUpdate,
    user: User = Depends(require_super_admin),
    db: AsyncSession = Depends(get_db_session),
) -> DishResponse:
    dish = await service.update_dish(dish_id, data, db)
    return DishResponse.model_validate(dish)


@router.post(
    "/dishes/{dish_id}/ingredients",
    response_model=DishIngredientResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_dish_ingredient(
    dish_id: uuid.UUID,
    data: DishIngredientCreate,
    user: User = Depends(require_super_admin),
    db: AsyncSession = Depends(get_db_session),
) -> DishIngredientResponse:
    di = await service.add_dish_ingredient(dish_id, data, db)
    return DishIngredientResponse.model_validate(di)


@router.get("/dishes/{dish_id}/ingredients", response_model=list[DishIngredientResponse])
async def list_dish_ingredients(
    dish_id: uuid.UUID,
    user: User = Depends(require_manager_or_above),
    db: AsyncSession = Depends(get_db_session),
) -> list[DishIngredientResponse]:
    items = await service.list_dish_ingredients(dish_id, db)
    return [DishIngredientResponse.model_validate(i) for i in items]


@router.delete(
    "/dishes/{dish_id}/ingredients/{ingredient_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_dish_ingredient(
    dish_id: uuid.UUID,
    ingredient_id: uuid.UUID,
    user: User = Depends(require_super_admin),
    db: AsyncSession = Depends(get_db_session),
) -> None:
    await service.delete_dish_ingredient(dish_id, ingredient_id, db)
