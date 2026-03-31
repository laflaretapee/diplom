"""
Prepare a point_manager with telegram_chat_id for notification verification.
"""
from __future__ import annotations

import asyncio
import sys

import bcrypt
from sqlalchemy import delete, select

sys.path.insert(0, "/workspace")

import backend.app.models.franchisee  # noqa: F401
import backend.app.models.franchisee_task  # noqa: F401
import backend.app.models.user  # noqa: F401
import backend.app.models.user_point  # noqa: F401
from backend.app.db.session import SessionLocal
from backend.app.models.point import Point
from backend.app.models.user import User, UserRole
from backend.app.models.user_point import UserPoint

EMAIL = "notify-manager@japonica.example.com"
PASSWORD = "Notify1234!"
CHAT_ID = "777888999"


def _hash(plain: str) -> str:
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()


async def main() -> None:
    async with SessionLocal() as db:
        point = (await db.execute(select(Point).limit(1))).scalar_one_or_none()
        if point is None:
            raise RuntimeError("No point found")

        existing = (await db.execute(select(User).where(User.email == EMAIL))).scalar_one_or_none()
        if existing is not None:
            await db.execute(delete(UserPoint).where(UserPoint.user_id == existing.id))
            await db.delete(existing)
            await db.flush()

        user = User(
            email=EMAIL,
            password_hash=_hash(PASSWORD),
            name="Notify Manager",
            role=UserRole.POINT_MANAGER,
            telegram_chat_id=CHAT_ID,
            is_active=True,
        )
        db.add(user)
        await db.flush()
        db.add(UserPoint(user_id=user.id, point_id=point.id))
        await db.commit()
        print(point.id)


if __name__ == "__main__":
    asyncio.run(main())
