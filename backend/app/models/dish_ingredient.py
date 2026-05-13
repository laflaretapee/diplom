from __future__ import annotations

import uuid
from decimal import Decimal

from sqlalchemy import ForeignKey, Numeric, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.db.base import Base
from backend.app.models.base import UUIDMixin


class DishIngredient(UUIDMixin, Base):
    __tablename__ = "dish_ingredients"

    __table_args__ = (
        UniqueConstraint("dish_id", "ingredient_id", name="uq_dish_ingredients_dish_ingredient"),
    )

    dish_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("dishes.id", ondelete="CASCADE"),
        nullable=False,
    )
    ingredient_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("ingredients.id"),
        nullable=False,
    )
    quantity_per_portion: Mapped[Decimal] = mapped_column(
        Numeric(10, 3), nullable=False
    )
