from __future__ import annotations

import enum
from typing import TYPE_CHECKING, Any

from sqlalchemy import JSON, Boolean, Enum, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.db.base import Base
from backend.app.models.base import TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from backend.app.models.user_point import UserPoint


class UserRole(str, enum.Enum):
    SUPER_ADMIN = "super_admin"
    FRANCHISEE = "franchisee"
    POINT_MANAGER = "point_manager"
    STAFF = "staff"


class User(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole, name="user_role", native_enum=False),
        nullable=False,
        default=UserRole.STAFF,
    )
    telegram_chat_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    notification_settings: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        default=dict,
        nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    points: Mapped[list[UserPoint]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )
