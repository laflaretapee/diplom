from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field

from backend.app.models.customer import CustomerSource


class CustomerCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    phone: str | None = Field(default=None, max_length=64)
    delivery_address: str | None = Field(default=None, max_length=500)
    telegram_id: str | None = Field(default=None, max_length=64)
    vk_id: str | None = Field(default=None, max_length=64)
    source: CustomerSource = CustomerSource.CRM
    notes: str | None = None


class CustomerUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    phone: str | None = Field(default=None, max_length=64)
    delivery_address: str | None = Field(default=None, max_length=500)
    telegram_id: str | None = Field(default=None, max_length=64)
    vk_id: str | None = Field(default=None, max_length=64)
    source: CustomerSource | None = None
    notes: str | None = None


class CustomerOrderSummary(BaseModel):
    id: uuid.UUID
    point_id: uuid.UUID
    status: str
    payment_status: str
    source_channel: str
    total_amount: Decimal
    created_at: datetime


class CustomerRead(BaseModel):
    id: uuid.UUID
    name: str
    phone: str | None
    delivery_address: str | None
    telegram_id: str | None
    vk_id: str | None
    source: CustomerSource
    notes: str | None
    created_at: datetime
    updated_at: datetime
    orders_count: int = 0
    total_spent: Decimal = Decimal("0")

    model_config = {"from_attributes": True}


class CustomerDetail(CustomerRead):
    orders: list[CustomerOrderSummary] = Field(default_factory=list)
