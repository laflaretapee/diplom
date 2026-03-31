from __future__ import annotations

import uuid
from datetime import date
from typing import TYPE_CHECKING, Any

from sqlalchemy import JSON, Boolean, Date, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.db.base import Base
from backend.app.models.base import TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from backend.app.models.franchisee import Franchisee
    from backend.app.models.user_point import UserPoint


class Point(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "points"

    franchisee_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("franchisees.id", ondelete="SET NULL"),
        nullable=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    address: Mapped[str] = mapped_column(String(500), nullable=False)
    payment_types: Mapped[list[Any]] = mapped_column(JSON, default=list, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    opened_at: Mapped[date | None] = mapped_column(Date, nullable=True)

    users: Mapped[list[UserPoint]] = relationship(
        back_populates="point",
        cascade="all, delete-orphan",
    )
    franchisee: Mapped[Franchisee | None] = relationship(
        "Franchisee",
        primaryjoin="Point.franchisee_id == Franchisee.id",
        foreign_keys="[Point.franchisee_id]",
        back_populates="points",
    )
