from __future__ import annotations

import asyncio
import sys
import uuid

import bcrypt
from sqlalchemy import delete, select

sys.path.insert(0, "/workspace")

import backend.app.models.franchisee  # noqa: F401
import backend.app.models.franchisee_task  # noqa: F401
import backend.app.models.user  # noqa: F401
import backend.app.models.user_point  # noqa: F401
from backend.app.db.session import SessionLocal
from backend.app.models.ingredient import Ingredient
from backend.app.models.point import Point
from backend.app.models.user import User, UserRole
from backend.app.models.user_point import UserPoint
from backend.app.tasks.notifications import (
    send_low_stock_notification,
    send_order_notification,
)

EMAIL = "prefs-manager@japonica.example.com"
CHAT_ID = "100200300"


def _hash(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


async def seed() -> tuple[str, str]:
    async with SessionLocal() as db:
        existing = (await db.execute(select(User).where(User.email == EMAIL))).scalar_one_or_none()
        if existing is not None:
            await db.execute(delete(UserPoint).where(UserPoint.user_id == existing.id))
            await db.delete(existing)
            await db.flush()

        point = Point(
            name=f"Prefs Point {uuid.uuid4().hex[:6]}",
            address="Verification street",
            payment_types=[],
            is_active=True,
        )
        ingredient = Ingredient(
            name=f"Prefs Rice {uuid.uuid4().hex[:6]}",
            unit="kg",
            min_stock_level=5,
            is_active=True,
        )
        user = User(
            email=EMAIL,
            password_hash=_hash("Prefs1234!"),
            name="Prefs Manager",
            role=UserRole.POINT_MANAGER,
            telegram_chat_id=CHAT_ID,
            notification_settings={
                "order_created": False,
                "order_cancelled": True,
                "low_stock": False,
            },
            is_active=True,
        )
        db.add_all([point, ingredient, user])
        await db.flush()
        db.add(UserPoint(user_id=user.id, point_id=point.id))
        await db.commit()
        return str(point.id), str(ingredient.id)


def main() -> None:
    point_id, ingredient_id = asyncio.run(seed())

    created = send_order_notification.delay(
        str(uuid.uuid4()),
        point_id,
        "order_created",
        [],
        "1450.00",
        "new",
    ).get(timeout=30)
    assert created["status"] == "skipped", created

    cancelled = send_order_notification.delay(
        str(uuid.uuid4()),
        point_id,
        "order_cancelled",
        [],
        "1450.00",
        "cancelled",
    ).get(timeout=30)
    assert cancelled["status"] == "sent", cancelled
    assert any(item["chat_id"] == CHAT_ID for item in cancelled["recipients"]), cancelled

    low_stock = send_low_stock_notification.delay(
        ingredient_id,
        point_id,
        2.0,
        5.0,
    ).get(timeout=30)
    assert low_stock["status"] == "skipped", low_stock

    print("PASS: notification preferences filter order_created/low_stock and allow order_cancelled")


if __name__ == "__main__":
    main()
