from __future__ import annotations

from decimal import Decimal
from typing import Final, Iterable

from sqlalchemy import JSON, Boolean, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.db.base import Base
from backend.app.models.base import TimestampMixin, UUIDMixin
from backend.app.models.order import SourceChannel

DISH_SALES_CHANNELS: Final[list[str]] = [channel.value for channel in SourceChannel]
INBOUND_SOURCE_CHANNELS: Final[set[str]] = {
    SourceChannel.WEBSITE.value,
    SourceChannel.MOBILE_APP.value,
    SourceChannel.TELEGRAM.value,
    SourceChannel.VK.value,
}


def normalize_dish_sales_channels(
    channels: Iterable[str | SourceChannel] | None,
) -> list[str]:
    if channels is None:
        return list(DISH_SALES_CHANNELS)

    requested = {
        channel.value if isinstance(channel, SourceChannel) else channel
        for channel in channels
    }
    unknown = requested.difference(DISH_SALES_CHANNELS)
    if unknown:
        unknown_list = ", ".join(sorted(unknown))
        raise ValueError(f"Unknown dish sales channels: {unknown_list}")
    return [channel for channel in DISH_SALES_CHANNELS if channel in requested]


def is_inbound_source_channel(channel: SourceChannel | str) -> bool:
    channel_value = channel.value if isinstance(channel, SourceChannel) else channel
    return channel_value in INBOUND_SOURCE_CHANNELS


class Dish(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "dishes"

    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    available_channels: Mapped[list[str]] = mapped_column(
        JSON,
        default=lambda: list(DISH_SALES_CHANNELS),
        nullable=False,
    )
