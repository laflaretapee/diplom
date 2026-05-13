from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field

from backend.app.models.order import OrderStatus, PaymentStatus, PaymentType, SourceChannel


class OrderItem(BaseModel):
    dish_id: uuid.UUID | None = None
    name: str
    quantity: int = Field(gt=0)
    price: Decimal = Field(gt=0)


class OrderCreate(BaseModel):
    point_id: uuid.UUID
    customer_id: uuid.UUID | None = None
    payment_type: PaymentType
    source_channel: SourceChannel
    items: list[OrderItem] = Field(min_length=1)
    delivery_address: str | None = None
    notes: str | None = None


class OrderStatusUpdate(BaseModel):
    status: OrderStatus


class OrderRead(BaseModel):
    id: uuid.UUID
    point_id: uuid.UUID
    customer_id: uuid.UUID | None = None
    status: OrderStatus
    payment_type: PaymentType
    payment_status: PaymentStatus
    source_channel: SourceChannel
    items: list[Any]
    total_amount: Decimal
    delivery_address: str | None = None
    payment_provider: str | None = None
    payment_invoice_id: str | None = None
    notes: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
