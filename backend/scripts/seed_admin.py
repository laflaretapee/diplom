"""Seed a super_admin user for local testing."""
import asyncio
import sys

import bcrypt

sys.path.insert(0, "/workspace")

from sqlalchemy import delete

from backend.app.db.session import SessionLocal
from backend.app.models.user import User, UserRole

ADMIN_EMAIL = "admin@japonica.example.com"
ADMIN_PASSWORD = "Admin1234!"


def _hash(plain: str) -> str:
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()


async def main() -> None:
    async with SessionLocal() as db:
        # Delete any stale test users with this email first
        await db.execute(delete(User).where(User.email == ADMIN_EMAIL))
        user = User(
            email=ADMIN_EMAIL,
            password_hash=_hash(ADMIN_PASSWORD),
            name="Super Admin",
            role=UserRole.SUPER_ADMIN,
            is_active=True,
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)
        print(f"Seeded admin id={user.id} email={user.email}")


asyncio.run(main())
