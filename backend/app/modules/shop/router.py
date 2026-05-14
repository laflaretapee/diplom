from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import PlainTextResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.db.session import get_db_session
from backend.app.models.customer import Customer, CustomerSource
from backend.app.models.dish import Dish
from backend.app.models.order import Order, PaymentStatus, PaymentType, SourceChannel
from backend.app.models.point import Point
from backend.app.modules.customers.service import upsert_customer_from_channel
from backend.app.modules.orders.schemas import OrderCreate, OrderItem
from backend.app.modules.orders.service import create_order
from backend.app.modules.shop.robokassa import build_payment_url, validate_result_signature
from backend.app.modules.shop.schemas import (
    ShopDish,
    ShopPoint,
    TelegramCatalogResponse,
    TelegramCheckoutRequest,
    TelegramCheckoutResponse,
    TelegramCustomerProfile,
)

router = APIRouter(prefix="/shop/telegram", tags=["telegram-shop"])


@router.get("/catalog", response_model=TelegramCatalogResponse)
async def telegram_catalog(
    db: AsyncSession = Depends(get_db_session),
) -> TelegramCatalogResponse:
    points_result = await db.execute(
        select(Point).where(Point.is_active).order_by(Point.created_at.asc())
    )
    dishes_result = await db.execute(
        select(Dish).where(Dish.is_active).order_by(Dish.name.asc())
    )
    dishes = [
        dish
        for dish in dishes_result.scalars().all()
        if SourceChannel.TELEGRAM.value in dish.available_channels
    ]
    points = points_result.scalars().all()
    return TelegramCatalogResponse(
        points=[ShopPoint.model_validate(point, from_attributes=True) for point in points],
        dishes=[ShopDish.model_validate(dish, from_attributes=True) for dish in dishes],
    )


@router.get("/customer", response_model=TelegramCustomerProfile)
async def telegram_customer(
    telegram_id: str,
    db: AsyncSession = Depends(get_db_session),
) -> TelegramCustomerProfile:
    result = await db.execute(select(Customer).where(Customer.telegram_id == telegram_id))
    customer = result.scalar_one_or_none()
    if customer is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found")
    return TelegramCustomerProfile.model_validate(customer, from_attributes=True)


@router.post(
    "/checkout",
    response_model=TelegramCheckoutResponse,
    status_code=status.HTTP_201_CREATED,
)
async def telegram_checkout(
    data: TelegramCheckoutRequest,
    db: AsyncSession = Depends(get_db_session),
) -> TelegramCheckoutResponse:
    point_result = await db.execute(select(Point).where(Point.id == data.point_id, Point.is_active))
    point = point_result.scalar_one_or_none()
    if point is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Point not found")

    dish_ids = [item.dish_id for item in data.items]
    dish_result = await db.execute(select(Dish).where(Dish.id.in_(dish_ids), Dish.is_active))
    dishes_by_id = {dish.id: dish for dish in dish_result.scalars().all()}
    order_items: list[OrderItem] = []
    for item in data.items:
        dish = dishes_by_id.get(item.dish_id)
        if dish is None:
            raise HTTPException(status_code=422, detail=f"Dish {item.dish_id} is unavailable")
        if (
            SourceChannel.TELEGRAM.value not in dish.available_channels
        ):
            raise HTTPException(
                status_code=422,
                detail=f"Dish {dish.name} is unavailable in Telegram",
            )
        order_items.append(
            OrderItem(dish_id=dish.id, name=dish.name, quantity=item.quantity, price=dish.price)
        )

    customer = await upsert_customer_from_channel(
        db,
        name=data.customer.name,
        phone=data.customer.phone,
        delivery_address=data.customer.delivery_address,
        telegram_id=data.customer.telegram_id,
        source=CustomerSource.TELEGRAM,
    )
    order = await create_order(
        OrderCreate(
            point_id=data.point_id,
            customer_id=customer.id,
            payment_type=PaymentType.ONLINE,
            source_channel=SourceChannel.TELEGRAM,
            items=order_items,
            delivery_address=data.customer.delivery_address,
            notes=data.notes,
        ),
        db,
    )
    invoice_id = str(int(datetime.now(tz=UTC).timestamp() * 1000))
    order.payment_provider = "robokassa"
    order.payment_invoice_id = invoice_id
    await db.commit()
    await db.refresh(order)
    payment_url = build_payment_url(
        out_sum=f"{order.total_amount:.2f}",
        invoice_id=invoice_id,
        description=f"Заказ {order.id}",
    )
    return TelegramCheckoutResponse(
        order_id=order.id,
        customer_id=customer.id,
        total_amount=order.total_amount,
        payment_url=payment_url,
    )


@router.api_route("/robokassa/result", methods=["GET", "POST"], response_class=PlainTextResponse)
async def robokassa_result(
    request: Request,
    db: AsyncSession = Depends(get_db_session),
) -> PlainTextResponse:
    payload = dict(request.query_params)
    if request.method == "POST":
        form = await request.form()
        payload.update(dict(form))
    out_sum = str(payload.get("OutSum", ""))
    invoice_id = str(payload.get("InvId", ""))
    signature = str(payload.get("SignatureValue", ""))
    if not out_sum or not invoice_id or not signature:
        raise HTTPException(status_code=400, detail="Missing Robokassa result parameters")
    if not validate_result_signature(out_sum=out_sum, invoice_id=invoice_id, signature=signature):
        raise HTTPException(status_code=400, detail="Invalid Robokassa signature")

    result = await db.execute(select(Order).where(Order.payment_invoice_id == invoice_id))
    order = result.scalar_one_or_none()
    if order is None:
        raise HTTPException(status_code=404, detail="Order not found")
    order.payment_status = PaymentStatus.PAID
    await db.commit()
    return PlainTextResponse(f"OK{invoice_id}")
