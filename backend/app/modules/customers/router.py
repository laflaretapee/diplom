from __future__ import annotations

import uuid
from decimal import Decimal

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.deps import require_manager_or_above
from backend.app.db.session import get_db_session
from backend.app.models.customer import Customer
from backend.app.models.order import Order
from backend.app.models.user import User
from backend.app.modules.customers import schemas as s
from backend.app.modules.customers import service

router = APIRouter(prefix="/customers", tags=["customers"])


def _to_read(customer: Customer, orders_count: int = 0, total_spent: Decimal = Decimal("0")):
    data = s.CustomerRead.model_validate(customer)
    data.orders_count = orders_count
    data.total_spent = total_spent
    return data


def _order_summary(order: Order) -> s.CustomerOrderSummary:
    return s.CustomerOrderSummary(
        id=order.id,
        point_id=order.point_id,
        status=order.status.value,
        payment_status=order.payment_status.value,
        source_channel=order.source_channel.value,
        total_amount=order.total_amount,
        created_at=order.created_at,
    )


@router.post("", response_model=s.CustomerRead, status_code=status.HTTP_201_CREATED)
async def create_customer(
    data: s.CustomerCreate,
    user: User = Depends(require_manager_or_above),
    db: AsyncSession = Depends(get_db_session),
) -> s.CustomerRead:
    customer = await service.create_customer(db, data)
    return _to_read(customer)


@router.get("", response_model=list[s.CustomerRead])
async def list_customers(
    query: str | None = Query(default=None),
    user: User = Depends(require_manager_or_above),
    db: AsyncSession = Depends(get_db_session),
) -> list[s.CustomerRead]:
    rows = await service.list_customers(db, query=query)
    return [
        _to_read(customer, orders_count, total_spent)
        for customer, orders_count, total_spent in rows
    ]


@router.get("/{customer_id}", response_model=s.CustomerDetail)
async def get_customer(
    customer_id: uuid.UUID,
    user: User = Depends(require_manager_or_above),
    db: AsyncSession = Depends(get_db_session),
) -> s.CustomerDetail:
    customer = await service.get_customer(db, customer_id)
    orders = await service.get_customer_orders(db, customer_id)
    detail = s.CustomerDetail.model_validate(customer)
    detail.orders = [_order_summary(order) for order in orders]
    detail.orders_count = len(orders)
    detail.total_spent = sum(
        (order.total_amount for order in orders if order.payment_status.value == "paid"),
        Decimal("0"),
    )
    return detail


@router.patch("/{customer_id}", response_model=s.CustomerRead)
async def update_customer(
    customer_id: uuid.UUID,
    data: s.CustomerUpdate,
    user: User = Depends(require_manager_or_above),
    db: AsyncSession = Depends(get_db_session),
) -> s.CustomerRead:
    customer = await service.update_customer(db, customer_id, data)
    return _to_read(customer)
