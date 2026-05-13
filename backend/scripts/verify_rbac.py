"""
Verify RBAC + tenant scoping:
1. Create two points and a staff user assigned only to point A.
2. Verify verify_point_access passes for point A, fails for point B.
3. Verify super_admin always passes.
"""
import asyncio
import sys

import bcrypt

sys.path.insert(0, "/workspace")

from sqlalchemy import delete

from backend.app.core.deps import verify_point_access
from backend.app.db.session import SessionLocal
from backend.app.models.point import Point
from backend.app.models.user import User, UserRole
from backend.app.models.user_point import UserPoint


def _hash(plain: str) -> str:
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()


async def main() -> None:
    async with SessionLocal() as db:
        # Cleanup
        await db.execute(delete(UserPoint))
        await db.execute(delete(User).where(User.email.in_([
            "staff@japonica.example.com",
            "admin@japonica.example.com",
        ])))
        await db.execute(delete(Point).where(Point.name.in_(["Point A", "Point B"])))
        await db.flush()

        # Create points
        point_a = Point(name="Point A", address="Addr A")
        point_b = Point(name="Point B", address="Addr B")
        db.add_all([point_a, point_b])
        await db.flush()

        # Create staff user
        staff = User(
            email="staff@japonica.example.com",
            password_hash=_hash("Staff1234!"),
            name="Staff User",
            role=UserRole.STAFF,
            is_active=True,
        )
        admin = User(
            email="admin@japonica.example.com",
            password_hash=_hash("Admin1234!"),
            name="Super Admin",
            role=UserRole.SUPER_ADMIN,
            is_active=True,
        )
        db.add_all([staff, admin])
        await db.flush()

        # Assign staff only to point_a
        db.add(UserPoint(user_id=staff.id, point_id=point_a.id))
        await db.commit()
        await db.refresh(staff)
        await db.refresh(admin)
        await db.refresh(point_a)
        await db.refresh(point_b)

        # Test 1: staff can access point_a
        try:
            await verify_point_access(point_a.id, staff, db)
            print("PASS: staff -> point_a allowed")
        except Exception as e:
            print(f"FAIL: staff -> point_a: {e}")

        # Test 2: staff cannot access point_b
        try:
            await verify_point_access(point_b.id, staff, db)
            print("FAIL: staff -> point_b should be denied")
        except Exception:
            print("PASS: staff -> point_b denied (403)")

        # Test 3: super_admin can access any point
        try:
            await verify_point_access(point_b.id, admin, db)
            print("PASS: super_admin -> point_b allowed (no restriction)")
        except Exception as e:
            print(f"FAIL: super_admin -> point_b: {e}")

        print("\nAll RBAC + tenant scoping checks done.")


asyncio.run(main())
