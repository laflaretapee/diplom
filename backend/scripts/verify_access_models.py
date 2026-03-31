from __future__ import annotations

import asyncio
import uuid

from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError

from backend.app.db.session import SessionLocal
from backend.app.models import Point, User, UserPoint, UserRole

USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")
POINT_A_ID = uuid.UUID("00000000-0000-0000-0000-000000000101")
POINT_B_ID = uuid.UUID("00000000-0000-0000-0000-000000000102")


async def cleanup() -> None:
    async with SessionLocal() as session:
        await session.execute(delete(UserPoint).where(UserPoint.user_id == USER_ID))
        await session.execute(delete(Point).where(Point.id.in_([POINT_A_ID, POINT_B_ID])))
        await session.execute(delete(User).where(User.id == USER_ID))
        await session.commit()


async def main() -> None:
    await cleanup()

    async with SessionLocal() as session:
        user = User(
            id=USER_ID,
            email="verify-access-models@example.com",
            password_hash="not-a-real-hash",
            name="Verifier",
            role=UserRole.POINT_MANAGER,
        )
        point_a = Point(id=POINT_A_ID, name="Point A", address="Addr A", payment_types=[])
        point_b = Point(id=POINT_B_ID, name="Point B", address="Addr B", payment_types=[])

        session.add_all([user, point_a, point_b])
        session.add_all(
            [
                UserPoint(user_id=USER_ID, point_id=POINT_A_ID),
                UserPoint(user_id=USER_ID, point_id=POINT_B_ID),
            ]
        )
        await session.commit()

    async with SessionLocal() as session:
        rows = await session.execute(select(UserPoint.user_id).where(UserPoint.user_id == USER_ID))
        links = rows.scalars().all()
        if len(links) != 2:
            raise RuntimeError(f"Expected 2 user-point links, got {len(links)}")

        session.add(UserPoint(user_id=USER_ID, point_id=POINT_A_ID))
        try:
            await session.commit()
        except IntegrityError:
            await session.rollback()
        else:
            raise RuntimeError("Expected duplicate user-point link to fail with IntegrityError")

    await cleanup()
    print("access models verification passed")


if __name__ == "__main__":
    asyncio.run(main())
