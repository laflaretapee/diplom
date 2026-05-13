from __future__ import annotations

import uuid
from datetime import date

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.deps import (
    require_any_role,
    require_manager_or_above,
    require_roles,
    verify_point_access,
)
from backend.app.db.session import get_db_session
from backend.app.models.order import OrderStatus
from backend.app.models.user import User, UserRole
from backend.app.modules.orders import service
from backend.app.modules.orders.schemas import OrderCreate, OrderRead, OrderStatusUpdate

router = APIRouter(prefix="/orders", tags=["orders"])


@router.post("", response_model=OrderRead, status_code=status.HTTP_201_CREATED)
async def create_order(
    data: OrderCreate,
    user: User = Depends(require_manager_or_above),
    db: AsyncSession = Depends(get_db_session),
) -> OrderRead:
    await verify_point_access(data.point_id, user, db)
    order = await service.create_order(data, db)
    return OrderRead.model_validate(order)


@router.get("", response_model=list[OrderRead])
async def list_orders(
    point_id: uuid.UUID,
    order_status: OrderStatus | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    user: User = Depends(require_any_role),
    db: AsyncSession = Depends(get_db_session),
) -> list[OrderRead]:
    await verify_point_access(point_id, user, db)
    orders = await service.list_orders(point_id, db, order_status, date_from, date_to)
    return [OrderRead.model_validate(o) for o in orders]


@router.get("/{order_id}", response_model=OrderRead)
async def get_order(
    order_id: uuid.UUID,
    user: User = Depends(require_any_role),
    db: AsyncSession = Depends(get_db_session),
) -> OrderRead:
    order = await service.get_order(order_id, db)
    # tenant check
    await verify_point_access(order.point_id, user, db)
    return OrderRead.model_validate(order)


@router.patch("/{order_id}/status", response_model=OrderRead)
async def update_order_status(
    order_id: uuid.UUID,
    data: OrderStatusUpdate,
    user: User = Depends(
        require_roles(
            UserRole.SUPER_ADMIN,
            UserRole.FRANCHISEE,
            UserRole.POINT_MANAGER,
            UserRole.STAFF,
        )
    ),
    db: AsyncSession = Depends(get_db_session),
) -> OrderRead:
    order = await service.get_order(order_id, db)
    await verify_point_access(order.point_id, user, db)
    updated = await service.update_order_status(order_id, data, db)
    return OrderRead.model_validate(updated)
