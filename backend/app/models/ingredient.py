from __future__ import annotations

from decimal import Decimal

from sqlalchemy import Boolean, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.db.base import Base
from backend.app.models.base import TimestampMixin, UUIDMixin


class Ingredient(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "ingredients"

    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    unit: Mapped[str] = mapped_column(String(50), nullable=False)
    min_stock_level: Mapped[Decimal] = mapped_column(
        Numeric(10, 3), nullable=False, default=Decimal("0")
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
