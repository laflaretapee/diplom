"""
TASK-020 verification: supply endpoint and movement history endpoint.
"""
from __future__ import annotations

import asyncio
import json
import sys
import urllib.request
import urllib.error

sys.path.insert(0, "/workspace")

BASE_URL = "http://172.20.0.5:8000/api/v1"


def http_post(url, data, headers=None):
    body = json.dumps(data).encode()
    req = urllib.request.Request(url, data=body, method="POST")
    req.add_header("Content-Type", "application/json")
    if headers:
        for k, v in headers.items():
            req.add_header(k, v)
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read())


def http_get(url, headers=None):
    req = urllib.request.Request(url, method="GET")
    if headers:
        for k, v in headers.items():
            req.add_header(k, v)
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read())


async def get_ids():
    import backend.app.models.franchisee  # noqa: F401
    import backend.app.models.franchisee_task  # noqa: F401
    import backend.app.models.user  # noqa: F401
    import backend.app.models.user_point  # noqa: F401
    from backend.app.db.session import SessionLocal
    from backend.app.models.point import Point
    from backend.app.models.ingredient import Ingredient
    from sqlalchemy import select

    async with SessionLocal() as db:
        r = await db.execute(select(Point).limit(1))
        point = r.scalar_one_or_none()
        r2 = await db.execute(select(Ingredient).limit(1))
        ingredient = r2.scalar_one_or_none()
        return str(point.id) if point else None, str(ingredient.id) if ingredient else None


def main():
    # Get token
    print("--- Login ---")
    token_data = http_post(
        f"{BASE_URL}/auth/login",
        {"email": "admin@japonica.example.com", "password": "Admin1234!"},
    )
    token = token_data["access_token"]
    print(f"Token obtained: {token[:20]}...")
    auth_header = {"Authorization": f"Bearer {token}"}

    # Get point_id and ingredient_id
    point_id, ing_id = asyncio.run(get_ids())
    print(f"point_id: {point_id}")
    print(f"ingredient_id: {ing_id}")

    if not point_id or not ing_id:
        print("ERROR: No point or ingredient in DB")
        sys.exit(1)

    # Test POST /warehouse/stock/supply
    print("\n--- POST /api/v1/warehouse/stock/supply ---")
    supply_resp = http_post(
        f"{BASE_URL}/warehouse/stock/supply",
        {
            "point_id": point_id,
            "ingredient_id": ing_id,
            "quantity": 50,
            "supplier_name": "ООО Рис-Опт",
        },
        headers=auth_header,
    )
    print(json.dumps(supply_resp, indent=2, ensure_ascii=False))

    assert "stock_item_id" in supply_resp, "Missing stock_item_id in response"
    assert "new_quantity" in supply_resp, "Missing new_quantity in response"
    assert "movement_id" in supply_resp, "Missing movement_id in response"
    print("Supply endpoint: OK")

    # Test GET /warehouse/stock/movements
    print("\n--- GET /api/v1/warehouse/stock/movements?point_id=... ---")
    url = f"{BASE_URL}/warehouse/stock/movements?point_id={point_id}&limit=5"
    movements_resp = http_get(url, headers=auth_header)
    print(json.dumps(movements_resp[:3], indent=2, ensure_ascii=False))

    assert isinstance(movements_resp, list), "Expected list response"
    assert len(movements_resp) > 0, "Expected at least 1 movement"
    first = movements_resp[0]
    assert "ingredient_name" in first, "Missing ingredient_name in movement"
    assert "movement_type" in first, "Missing movement_type in movement"
    assert "quantity" in first, "Missing quantity in movement"
    print(f"Movements endpoint: OK (returned {len(movements_resp)} movements)")

    print("\nSUCCESS: TASK-020 endpoints work correctly!")


if __name__ == "__main__":
    main()
