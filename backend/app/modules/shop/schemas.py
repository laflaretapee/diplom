from __future__ import annotations

import uuid
from decimal import Decimal

from pydantic import BaseModel, Field


class ShopPoint(BaseModel):
    id: uuid.UUID
    name: str
    address: str


class ShopDish(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None
    price: Decimal


class TelegramCatalogResponse(BaseModel):
    points: list[ShopPoint]
    dishes: list[ShopDish]


class TelegramCustomerProfile(BaseModel):
    name: str
    phone: str | None
    delivery_address: str | None
    telegram_id: str | None


class TelegramCheckoutItem(BaseModel):
    dish_id: uuid.UUID
    quantity: int = Field(gt=0, le=99)


class TelegramCustomerPayload(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    phone: str = Field(min_length=3, max_length=64)
    delivery_address: str = Field(min_length=3, max_length=500)
    telegram_id: str | None = Field(default=None, max_length=64)


class TelegramCheckoutRequest(BaseModel):
    point_id: uuid.UUID
    customer: TelegramCustomerPayload
    items: list[TelegramCheckoutItem] = Field(min_length=1)
    notes: str | None = None


class TelegramCheckoutResponse(BaseModel):
    order_id: uuid.UUID
    customer_id: uuid.UUID
    total_amount: Decimal
    payment_url: str
