from __future__ import annotations

import enum
import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field

from backend.app.models.order import OrderStatus, PaymentType, SourceChannel


class InboundSourceChannel(str, enum.Enum):
    WEBSITE = "website"
    MOBILE_APP = "mobile_app"
    TELEGRAM = "telegram"
    VK = "vk"


class InboundOrderItem(BaseModel):
    dish_id: uuid.UUID | None = None
    name: str
    quantity: int = Field(gt=0)
    price: Decimal = Field(gt=0)


class InboundOrderRequest(BaseModel):
    point_id: uuid.UUID
    source_channel: InboundSourceChannel
    payment_type: PaymentType
    items: list[InboundOrderItem] = Field(min_length=1)
    notes: str | None = None
    customer_name: str | None = None
    customer_phone: str | None = None


class InboundOrderResponse(BaseModel):
    id: uuid.UUID
    status: OrderStatus
    total_amount: Decimal
    source_channel: SourceChannel
    created_at: datetime

    model_config = {"from_attributes": True}
