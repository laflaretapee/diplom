"""
TASK-021 verification: warehouse audit endpoint shows author/system events and enforces tenant scope.
"""
from __future__ import annotations

import asyncio
import json
import sys
import urllib.error
import urllib.request
import uuid
from decimal import Decimal

import bcrypt
from sqlalchemy import delete, select

sys.path.insert(0, "/workspace")

import backend.app.models.franchisee  # noqa: F401
import backend.app.models.franchisee_task  # noqa: F401
import backend.app.models.user  # noqa: F401
import backend.app.models.user_point  # noqa: F401
from backend.app.db.session import SessionLocal
from backend.app.models.dish import Dish
from backend.app.models.dish_ingredient import DishIngredient
from backend.app.models.ingredient import Ingredient
from backend.app.models.point import Point
from backend.app.models.stock_item import StockItem
from backend.app.models.user import User, UserRole
from backend.app.models.user_point import UserPoint
from backend.app.modules.orders.schemas import OrderCreate, OrderItem
from backend.app.modules.orders.service import create_order
from backend.app.modules.warehouse.schemas import MovementCreate, SupplyCreate
from backend.app.modules.warehouse.service import create_movement, create_supply

BASE_URL = "http://127.0.0.1:8000/api/v1"
ADMIN_EMAIL = "admin@japonica.example.com"
ADMIN_PASSWORD = "Admin1234!"
MANAGER_EMAIL = "audit-manager@japonica.example.com"
MANAGER_PASSWORD = "Manager1234!"


def _hash(plain: str) -> str:
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()


def http_post(url: str, data: dict, headers: dict[str, str] | None = None) -> dict:
    body = json.dumps(data).encode()
    req = urllib.request.Request(url, data=body, method="POST")
    req.add_header("Content-Type", "application/json")
    if headers:
        for key, value in headers.items():
            req.add_header(key, value)
    with urllib.request.urlopen(req) as response:
        return json.loads(response.read())


def http_get(url: str, headers: dict[str, str] | None = None) -> list[dict]:
    req = urllib.request.Request(url, method="GET")
    if headers:
        for key, value in headers.items():
            req.add_header(key, value)
    with urllib.request.urlopen(req) as response:
        return json.loads(response.read())


async def prepare_fixture() -> tuple[str, str]:
    async with SessionLocal() as db:
        await db.execute(delete(UserPoint))
        await db.execute(delete(User).where(User.email.in_([ADMIN_EMAIL, MANAGER_EMAIL])))
        await db.execute(
            delete(Point).where(Point.name.in_(["Audit Point Allowed", "Audit Point Denied"]))
        )
        await db.flush()

        allowed_point = Point(name="Audit Point Allowed", address="Allowed address")
        denied_point = Point(name="Audit Point Denied", address="Denied address")
        db.add_all([allowed_point, denied_point])
        await db.flush()

        admin = User(
            email=ADMIN_EMAIL,
            password_hash=_hash(ADMIN_PASSWORD),
            name="Super Admin",
            role=UserRole.SUPER_ADMIN,
            is_active=True,
        )
        manager = User(
            email=MANAGER_EMAIL,
            password_hash=_hash(MANAGER_PASSWORD),
            name="Audit Manager",
            role=UserRole.POINT_MANAGER,
            is_active=True,
        )
        db.add_all([admin, manager])
        await db.flush()

        db.add(UserPoint(user_id=manager.id, point_id=allowed_point.id))
        await db.flush()

        ingredient = Ingredient(
            name=f"Audit Ingredient {uuid.uuid4().hex[:6]}",
            unit="kg",
            min_stock_level=Decimal("5"),
        )
        db.add(ingredient)
        await db.flush()

        await create_supply(
            SupplyCreate(
                point_id=allowed_point.id,
                ingredient_id=ingredient.id,
                quantity=Decimal("20"),
                supplier_name="Audit Supplier",
                note="audit-supply",
            ),
            created_by_id=admin.id,
            db=db,
        )

        stock_item_result = await db.execute(
            select(StockItem.id).where(
                StockItem.ingredient_id == ingredient.id,
                StockItem.point_id == allowed_point.id,
            )
        )
        stock_item_id = stock_item_result.scalar_one()

        await create_movement(
            MovementCreate(
                stock_item_id=stock_item_id,
                movement_type="adjustment",
                quantity=Decimal("18"),
                reason="audit-adjustment",
            ),
            created_by_id=manager.id,
            db=db,
        )

        dish = Dish(
            name=f"Audit Dish {uuid.uuid4().hex[:6]}",
            description="Triggers system write-off",
            price=Decimal("450"),
            is_active=True,
        )
        db.add(dish)
        await db.flush()
        db.add(
            DishIngredient(
                dish_id=dish.id,
                ingredient_id=ingredient.id,
                quantity_per_portion=Decimal("2"),
            )
        )
        await db.commit()

        await create_order(
            OrderCreate(
                point_id=allowed_point.id,
                payment_type="cash",
                source_channel="pos",
                items=[OrderItem(name=dish.name, quantity=1, price=Decimal("450"))],
            ),
            db=db,
        )

        return str(allowed_point.id), str(denied_point.id)


async def main() -> None:
    allowed_point_id, denied_point_id = await prepare_fixture()
    await asyncio.sleep(2)

    admin_token = http_post(
        f"{BASE_URL}/auth/login",
        {"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
    )["access_token"]
    manager_token = http_post(
        f"{BASE_URL}/auth/login",
        {"email": MANAGER_EMAIL, "password": MANAGER_PASSWORD},
    )["access_token"]

    admin_headers = {"Authorization": f"Bearer {admin_token}"}
    manager_headers = {"Authorization": f"Bearer {manager_token}"}

    audit_rows = http_get(
        f"{BASE_URL}/warehouse/audit?point_id={allowed_point_id}",
        headers=admin_headers,
    )
    assert isinstance(audit_rows, list) and audit_rows, "Expected non-empty audit response"

    supply_rows = [row for row in audit_rows if str(row.get("reason", "")).startswith("supply:")]
    adjustment_rows = [row for row in audit_rows if row.get("reason") == "audit-adjustment"]
    order_rows = [row for row in audit_rows if str(row.get("reason", "")).startswith("order:")]

    assert supply_rows, "Expected supply event in audit log"
    assert adjustment_rows, "Expected adjustment event in audit log"
    assert order_rows, "Expected system order write-off in audit log"
    assert supply_rows[0]["created_by_name"] == "Super Admin", "Supply author missing"
    assert adjustment_rows[0]["created_by_name"] == "Audit Manager", "Adjustment author missing"
    assert order_rows[0]["created_by_name"] is None, "System write-off should not have author"
    assert order_rows[0]["created_by_id"] is None, "System write-off should not have created_by_id"

    manager_allowed_rows = http_get(
        f"{BASE_URL}/warehouse/audit?point_id={allowed_point_id}",
        headers=manager_headers,
    )
    assert manager_allowed_rows, "Manager should access audit for assigned point"

    try:
        http_get(
            f"{BASE_URL}/warehouse/audit?point_id={denied_point_id}",
            headers=manager_headers,
        )
    except urllib.error.HTTPError as exc:
        assert exc.code == 403, f"Expected 403 for чужая точка, got {exc.code}"
    else:
        raise AssertionError("Expected manager audit request for foreign point to fail with 403")

    print("SUCCESS: audit endpoint returns author/system rows and enforces tenant access.")
    print(f"  allowed point: {allowed_point_id}")
    print(f"  denied point:  {denied_point_id}")
    print(f"  audit rows inspected: {len(audit_rows)}")


if __name__ == "__main__":
    asyncio.run(main())
