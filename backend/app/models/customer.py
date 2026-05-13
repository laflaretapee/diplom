from __future__ import annotations

import enum

from sqlalchemy import Enum as SAEnum
from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.db.base import Base
from backend.app.models.base import TimestampMixin, UUIDMixin


class CustomerSource(str, enum.Enum):
    CRM = "crm"
    TELEGRAM = "telegram"
    VK = "vk"
    WEBSITE = "website"


class Customer(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "customers"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(64), nullable=True)
    delivery_address: Mapped[str | None] = mapped_column(String(500), nullable=True)
    telegram_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    vk_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    source: Mapped[CustomerSource] = mapped_column(
        SAEnum(CustomerSource, name="customer_source", native_enum=False),
        nullable=False,
        default=CustomerSource.CRM,
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
