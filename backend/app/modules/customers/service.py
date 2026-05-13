from __future__ import annotations

import uuid
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy import case, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.customer import Customer, CustomerSource
from backend.app.models.order import Order, PaymentStatus
from backend.app.modules.customers.schemas import CustomerCreate, CustomerUpdate


async def upsert_customer_from_channel(
    db: AsyncSession,
    *,
    name: str,
    phone: str | None,
    delivery_address: str | None,
    telegram_id: str | None = None,
    vk_id: str | None = None,
    source: CustomerSource = CustomerSource.TELEGRAM,
) -> Customer:
    customer: Customer | None = None
    if telegram_id:
        result = await db.execute(select(Customer).where(Customer.telegram_id == telegram_id))
        customer = result.scalar_one_or_none()
    if customer is None and vk_id:
        result = await db.execute(select(Customer).where(Customer.vk_id == vk_id))
        customer = result.scalar_one_or_none()
    if customer is None and phone:
        result = await db.execute(select(Customer).where(Customer.phone == phone))
        customer = result.scalar_one_or_none()

    if customer is None:
        customer = Customer(
            name=name,
            phone=phone,
            delivery_address=delivery_address,
            telegram_id=telegram_id,
            vk_id=vk_id,
            source=source,
        )
        db.add(customer)
    else:
        customer.name = name or customer.name
        customer.phone = phone or customer.phone
        customer.delivery_address = delivery_address or customer.delivery_address
        customer.telegram_id = telegram_id or customer.telegram_id
        customer.vk_id = vk_id or customer.vk_id
        customer.source = source
    await db.flush()
    return customer


async def create_customer(db: AsyncSession, data: CustomerCreate) -> Customer:
    customer = Customer(**data.model_dump())
    db.add(customer)
    await db.commit()
    await db.refresh(customer)
    return customer


async def list_customers(
    db: AsyncSession,
    *,
    query: str | None = None,
    limit: int = 100,
) -> list[tuple[Customer, int, Decimal]]:
    paid_total = func.coalesce(
        func.sum(
            case(
                (Order.payment_status == PaymentStatus.PAID, Order.total_amount),
                else_=0,
            )
        ),
        0,
    )
    stmt = (
        select(
            Customer,
            func.count(Order.id).label("orders_count"),
            paid_total.label("total_spent"),
        )
        .outerjoin(Order, Order.customer_id == Customer.id)
        .group_by(Customer.id)
        .order_by(Customer.updated_at.desc())
        .limit(limit)
    )
    if query:
        like = f"%{query.strip()}%"
        stmt = stmt.where(
            or_(
                Customer.name.ilike(like),
                Customer.phone.ilike(like),
                Customer.telegram_id.ilike(like),
                Customer.vk_id.ilike(like),
            )
        )
    result = await db.execute(stmt)
    return [(row[0], int(row[1] or 0), Decimal(str(row[2] or 0))) for row in result.all()]


async def get_customer(db: AsyncSession, customer_id: uuid.UUID) -> Customer:
    result = await db.execute(select(Customer).where(Customer.id == customer_id))
    customer = result.scalar_one_or_none()
    if customer is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found")
    return customer


async def update_customer(
    db: AsyncSession,
    customer_id: uuid.UUID,
    data: CustomerUpdate,
) -> Customer:
    customer = await get_customer(db, customer_id)
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(customer, key, value)
    await db.commit()
    await db.refresh(customer)
    return customer


async def get_customer_orders(db: AsyncSession, customer_id: uuid.UUID) -> list[Order]:
    result = await db.execute(
        select(Order).where(Order.customer_id == customer_id).order_by(Order.created_at.desc())
    )
    return list(result.scalars().all())
