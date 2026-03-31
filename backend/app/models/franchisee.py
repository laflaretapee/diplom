from __future__ import annotations

import enum
import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Enum, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.db.base import Base
from backend.app.models.base import TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from backend.app.models.franchisee_task import FranchiseeTask
    from backend.app.models.point import Point


class FranchiseeStatus(str, enum.Enum):
    LEAD = "lead"
    NEGOTIATION = "negotiation"
    CONTRACT = "contract"
    TRAINING = "training"
    SETUP = "setup"
    OPEN = "open"
    ACTIVE = "active"
    TERMINATED = "terminated"


class Franchisee(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "franchisees"

    company_name: Mapped[str] = mapped_column(String(255), nullable=False)
    contact_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    contact_email: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    contact_phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    status: Mapped[FranchiseeStatus] = mapped_column(
        Enum(FranchiseeStatus, name="franchisee_status", native_enum=False),
        nullable=False,
        default=FranchiseeStatus.LEAD,
    )
    responsible_owner_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    tasks: Mapped[list[FranchiseeTask]] = relationship(
        back_populates="franchisee",
        cascade="all, delete-orphan",
    )
    points: Mapped[list[Point]] = relationship(
        "Point",
        primaryjoin="Point.franchisee_id == Franchisee.id",
        foreign_keys="Point.franchisee_id",
        back_populates="franchisee",
    )
