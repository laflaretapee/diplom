from __future__ import annotations

import enum
import uuid
from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import Date, DateTime, Enum, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.db.base import Base
from backend.app.models.base import UUIDMixin
from backend.app.models.franchisee import FranchiseeStatus

if TYPE_CHECKING:
    from backend.app.models.franchisee import Franchisee


class TaskStatus(str, enum.Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    DONE = "done"
    SKIPPED = "skipped"


class FranchiseeTask(UUIDMixin, Base):
    __tablename__ = "franchisee_tasks"

    franchisee_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("franchisees.id", ondelete="CASCADE"),
        nullable=False,
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    stage: Mapped[FranchiseeStatus] = mapped_column(
        Enum(FranchiseeStatus, name="franchisee_status", native_enum=False),
        nullable=False,
    )
    status: Mapped[TaskStatus] = mapped_column(
        Enum(TaskStatus, name="task_status", native_enum=False),
        nullable=False,
        default=TaskStatus.PENDING,
    )
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    franchisee: Mapped[Franchisee] = relationship(back_populates="tasks")
