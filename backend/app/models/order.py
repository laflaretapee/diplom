from __future__ import annotations

import enum
import uuid
from decimal import Decimal
from typing import Any

from sqlalchemy import JSON, ForeignKey, Numeric, Text
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.db.base import Base
from backend.app.models.base import TimestampMixin, UUIDMixin


class OrderStatus(str, enum.Enum):
    NEW = "new"
    IN_PROGRESS = "in_progress"
    READY = "ready"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"


class PaymentType(str, enum.Enum):
    CASH = "cash"
    CARD = "card"
    ONLINE = "online"


class PaymentStatus(str, enum.Enum):
    PENDING = "pending"
    PAID = "paid"
    FAILED = "failed"
    REFUNDED = "refunded"


class SourceChannel(str, enum.Enum):
    WEBSITE = "website"
    MOBILE_APP = "mobile_app"
    TELEGRAM = "telegram"
    VK = "vk"
    POS = "pos"


class Order(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "orders"

    point_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("points.id", ondelete="CASCADE"),
        nullable=False,
    )
    status: Mapped[OrderStatus] = mapped_column(
        SAEnum(OrderStatus, name="order_status", native_enum=False),
        nullable=False,
        default=OrderStatus.NEW,
    )
    payment_type: Mapped[PaymentType] = mapped_column(
        SAEnum(PaymentType, name="payment_type", native_enum=False),
        nullable=False,
    )
    payment_status: Mapped[PaymentStatus] = mapped_column(
        SAEnum(PaymentStatus, name="payment_status", native_enum=False),
        nullable=False,
        default=PaymentStatus.PENDING,
    )
    source_channel: Mapped[SourceChannel] = mapped_column(
        SAEnum(SourceChannel, name="source_channel", native_enum=False),
        nullable=False,
    )
    items: Mapped[list[Any]] = mapped_column(JSON, nullable=False, default=list)
    total_amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
