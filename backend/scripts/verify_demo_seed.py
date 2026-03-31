from __future__ import annotations

import argparse
import asyncio
import json
import sys
import urllib.error
import urllib.parse
import urllib.request
import uuid
from collections import Counter
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.db.session import SessionLocal
from backend.app.models.dish import Dish
from backend.app.models.dish_ingredient import DishIngredient
from backend.app.models.franchisee import Franchisee
from backend.app.models.franchisee_task import FranchiseeTask
from backend.app.models.ingredient import Ingredient
from backend.app.models.order import Order
from backend.app.models.point import Point
from backend.app.models.stock_item import StockItem
from backend.app.models.stock_movement import StockMovement
from backend.app.models.user import User, UserRole
from backend.app.models.user_point import UserPoint
from backend.app.modules.auth.service import authenticate_user, build_login_response
from backend.scripts.seed_demo import cleanup_owned_demo_graph

DEMO_PREFIX = "[DEMO]"
FIXED_USERS = {
    "admin": ("admin@japonica.example.com", "Admin1234!", UserRole.SUPER_ADMIN),
    "franchisee": ("franchisee-ufa1@japonica.example.com", "Demo1234!", UserRole.FRANCHISEE),
    "manager": ("manager-ufa1@japonica.example.com", "Demo1234!", UserRole.POINT_MANAGER),
    "staff": ("staff-ufa1@japonica.example.com", "Demo1234!", UserRole.STAFF),
}
DEFAULT_BASE_URLS = (
    "http://127.0.0.1:18000/api/v1",
    "http://127.0.0.1:8000/api/v1",
)


def expect(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def _json_request(
    url: str,
    *,
    method: str = "GET",
    data: dict | None = None,
    headers: dict[str, str] | None = None,
) -> tuple[int, dict | list]:
    payload = None
    request_headers = dict(headers or {})
    if data is not None:
        payload = json.dumps(data).encode()
        request_headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=payload, method=method)
    for key, value in request_headers.items():
        request.add_header(key, value)
    with urllib.request.urlopen(request) as response:
        raw = response.read()
        return response.status, json.loads(raw)


def api_get(base_url: str, path: str, *, token: str | None = None, query: dict | None = None) -> dict | list:
    url = f"{base_url}{path}"
    if query:
        url = f"{url}?{urllib.parse.urlencode(query)}"
    headers = {"Authorization": f"Bearer {token}"} if token else None
    _, payload = _json_request(url, headers=headers)
    return payload


def api_post(base_url: str, path: str, body: dict, *, token: str | None = None) -> dict | list:
    headers = {"Authorization": f"Bearer {token}"} if token else None
    _, payload = _json_request(f"{base_url}{path}", method="POST", data=body, headers=headers)
    return payload


def detect_base_url(explicit_base_url: str | None) -> str:
    candidates = (explicit_base_url,) if explicit_base_url else DEFAULT_BASE_URLS
    for candidate in candidates:
        try:
            payload = api_get(candidate, "/analytics/status")
        except urllib.error.URLError:
            continue
        except urllib.error.HTTPError:
            continue
        expect(isinstance(payload, dict) and payload.get("module") == "analytics", f"Unexpected status payload from {candidate}")
        return candidate
    checked = ", ".join(candidate for candidate in candidates if candidate)
    raise RuntimeError(f"API is not reachable on any known base URL: {checked}")


async def load_demo_state(db: AsyncSession) -> dict[str, object]:
    user_result = await db.execute(
        select(User).where(User.email.in_([item[0] for item in FIXED_USERS.values()]))
    )
    users = list(user_result.scalars().all())
    expect(len(users) == 4, f"Expected 4 fixed demo users, got {len(users)}")

    users_by_email = {user.email: user for user in users}
    for label, (email, _password, role) in FIXED_USERS.items():
        user = users_by_email.get(email)
        expect(user is not None, f"Missing demo user {email}")
        expect(user.role == role, f"Unexpected role for {email}: {user.role}")
        expect(user.is_active, f"Demo user {email} must be active")

    point_result = await db.execute(
        select(Point).where(Point.name.like(f"{DEMO_PREFIX}%")).order_by(Point.name)
    )
    points = list(point_result.scalars().all())
    expect(2 <= len(points) <= 3, f"Expected 2-3 demo points, got {len(points)}")

    ingredient_result = await db.execute(
        select(Ingredient).where(Ingredient.name.like(f"{DEMO_PREFIX}%")).order_by(Ingredient.name)
    )
    ingredients = list(ingredient_result.scalars().all())
    expect(8 <= len(ingredients) <= 15, f"Expected 8-15 demo ingredients, got {len(ingredients)}")

    dish_result = await db.execute(
        select(Dish).where(Dish.name.like(f"{DEMO_PREFIX}%")).order_by(Dish.name)
    )
    dishes = list(dish_result.scalars().all())
    expect(6 <= len(dishes) <= 10, f"Expected 6-10 demo dishes, got {len(dishes)}")

    franchisee_result = await db.execute(
        select(Franchisee).where(Franchisee.company_name.like(f"{DEMO_PREFIX}%")).order_by(Franchisee.company_name)
    )
    franchisees = list(franchisee_result.scalars().all())
    expect(1 <= len(franchisees) <= 3, f"Expected 1-3 demo franchisees, got {len(franchisees)}")
    expect(len({item.status for item in franchisees}) >= 3, "Expected franchisees in at least 3 distinct stages")

    point_ids = [point.id for point in points]
    dish_ids = [dish.id for dish in dishes]
    ingredient_ids = [ingredient.id for ingredient in ingredients]
    franchisee_ids = [franchisee.id for franchisee in franchisees]

    order_result = await db.execute(
        select(Order).where(Order.point_id.in_(point_ids)).order_by(Order.created_at)
    )
    orders = list(order_result.scalars().all())
    expect(10 <= len(orders) <= 20, f"Expected 10-20 demo orders, got {len(orders)}")
    expect(orders[0].created_at is not None and orders[-1].created_at is not None, "Demo orders must have created_at")
    expect((orders[-1].created_at - orders[0].created_at).days >= 14, "Demo orders must cover at least two weeks")
    expect(orders[-1].created_at.date() == datetime.now(UTC).date(), "Expected at least one demo order today")

    task_result = await db.execute(
        select(FranchiseeTask).where(FranchiseeTask.franchisee_id.in_(franchisee_ids))
    )
    franchisee_tasks = list(task_result.scalars().all())
    expect(len(franchisee_tasks) >= 3, "Expected demo franchisee tasks")

    user_point_result = await db.execute(
        select(UserPoint).where(UserPoint.point_id.in_(point_ids))
    )
    user_points = list(user_point_result.scalars().all())
    expect(len(user_points) >= 2, "Expected demo user-point assignments")

    dish_ingredient_result = await db.execute(
        select(DishIngredient).where(
            DishIngredient.dish_id.in_(dish_ids),
            DishIngredient.ingredient_id.in_(ingredient_ids),
        )
    )
    dish_ingredients = list(dish_ingredient_result.scalars().all())
    expect(len(dish_ingredients) >= len(dishes), "Expected recipe rows for demo dishes")

    stock_item_result = await db.execute(
        select(StockItem).where(StockItem.point_id.in_(point_ids))
    )
    stock_items = list(stock_item_result.scalars().all())
    expect(len(stock_items) >= len(points) * 8, "Expected stock items for demo points")

    stock_item_ids = [item.id for item in stock_items]
    movement_result = await db.execute(
        select(StockMovement).where(StockMovement.stock_item_id.in_(stock_item_ids))
    )
    stock_movements = list(movement_result.scalars().all())
    expect(len(stock_movements) >= len(points) * 5, "Expected stock movement history for demo points")

    franchisee_by_email = {item.contact_email: item for item in franchisees}
    main_franchisee = franchisee_by_email.get("ufa-owner@japonica.example.com")
    expect(main_franchisee is not None, "Missing main demo franchisee")
    ufa1 = next((point for point in points if point.name == f"{DEMO_PREFIX} Ufa 1"), None)
    expect(ufa1 is not None, "Missing main demo point [DEMO] Ufa 1")

    manager = users_by_email["manager-ufa1@japonica.example.com"]
    staff = users_by_email["staff-ufa1@japonica.example.com"]
    ufa1_assignments = Counter(item.user_id for item in user_points if item.point_id == ufa1.id)
    expect(ufa1_assignments[manager.id] == 1, "Manager must be assigned to [DEMO] Ufa 1")
    expect(ufa1_assignments[staff.id] == 1, "Staff must be assigned to [DEMO] Ufa 1")

    return {
        "users_by_email": users_by_email,
        "points": points,
        "points_by_name": {point.name: point for point in points},
        "franchisees": franchisees,
        "main_franchisee": main_franchisee,
        "orders": orders,
    }


async def verify_cleanup_safety(db: AsyncSession) -> None:
    ingredient_result = await db.execute(select(Ingredient).where(Ingredient.name == f"{DEMO_PREFIX} Rice"))
    demo_ingredient = ingredient_result.scalar_one_or_none()
    expect(demo_ingredient is not None, "Missing [DEMO] Rice for cleanup safety check")

    savepoint = await db.begin_nested()
    try:
        now = datetime.now(UTC)
        temp_point = Point(
            id=uuid.uuid4(),
            name="QA Non Demo Safety Point",
            address="QA street",
            payment_types=[],
            is_active=True,
            opened_at=now.date(),
        )
        temp_stock_item = StockItem(
            id=uuid.uuid4(),
            ingredient_id=demo_ingredient.id,
            point_id=temp_point.id,
            quantity=Decimal("1.000"),
            updated_at=now,
        )
        temp_dish = Dish(
            id=uuid.uuid4(),
            name="QA Non Demo Safety Dish",
            description=None,
            price=Decimal("100.00"),
            is_active=True,
            created_at=now,
            updated_at=now,
        )
        temp_recipe = DishIngredient(
            id=uuid.uuid4(),
            dish_id=temp_dish.id,
            ingredient_id=demo_ingredient.id,
            quantity_per_portion=Decimal("0.100"),
        )

        db.add(temp_point)
        db.add(temp_stock_item)
        db.add(temp_dish)
        db.add(temp_recipe)
        await db.flush()

        await cleanup_owned_demo_graph(db)

        stock_exists = await db.execute(select(StockItem.id).where(StockItem.id == temp_stock_item.id))
        expect(
            stock_exists.scalar_one_or_none() == temp_stock_item.id,
            "cleanup must not delete stock items outside demo points",
        )

        recipe_exists = await db.execute(select(DishIngredient.id).where(DishIngredient.id == temp_recipe.id))
        expect(
            recipe_exists.scalar_one_or_none() == temp_recipe.id,
            "cleanup must not delete dish recipes outside demo dishes",
        )
    finally:
        await savepoint.rollback()


async def verify_logins(db: AsyncSession) -> dict[str, str]:
    tokens: dict[str, str] = {}
    for label, (email, password, _role) in FIXED_USERS.items():
        user = await authenticate_user(email, password, db)
        login_response, _refresh_token = build_login_response(user)
        expect(login_response.user.email == email, f"Unexpected authenticated user payload for {email}")
        expect(login_response.access_token, f"Missing access token for {email}")
        tokens[label] = login_response.access_token
    return tokens


def verify_api(base_url: str, tokens: dict[str, str], ids: dict[str, str]) -> None:
    admin_token = tokens["admin"]
    manager_token = tokens["manager"]
    franchisee_token = tokens["franchisee"]
    staff_token = tokens["staff"]

    admin_points = api_get(base_url, "/points", token=admin_token)
    expect(isinstance(admin_points, list) and len(admin_points) >= 3, "Admin points list must include demo points")

    manager_points = api_get(base_url, "/points", token=manager_token)
    expect(isinstance(manager_points, list) and len(manager_points) == 1, "Manager must see exactly one assigned point")
    expect(manager_points[0]["name"] == f"{DEMO_PREFIX} Ufa 1", "Manager must see [DEMO] Ufa 1")

    staff_points = api_get(base_url, "/points", token=staff_token)
    expect(isinstance(staff_points, list) and len(staff_points) == 1, "Staff must see exactly one assigned point")

    franchisee_points = api_get(base_url, "/points", token=franchisee_token)
    expect(isinstance(franchisee_points, list) and len(franchisee_points) >= 2, "Franchisee must see owned points")

    revenue = api_get(base_url, "/analytics/revenue", token=admin_token, query={"period": "week"})
    expect(isinstance(revenue, list) and len(revenue) >= 1, "Revenue analytics must return rows")

    dishes = api_get(base_url, "/analytics/dishes", token=admin_token, query={"period": "week", "point_id": ids["point_id"], "limit": 5})
    expect(isinstance(dishes, dict) and dishes.get("top") and dishes.get("bottom"), "Dishes analytics must be populated")

    channels = api_get(base_url, "/analytics/channels", token=admin_token, query={"period": "week", "point_id": ids["point_id"]})
    expect(isinstance(channels, list) and len(channels) >= 2, "Channel analytics must be populated")

    summary = api_get(base_url, "/analytics/summary", token=manager_token, query={"point_id": ids["point_id"]})
    expect(isinstance(summary, dict) and summary.get("total_orders_today", 0) >= 1, "Manager summary must include today's orders")
    expect(summary.get("pending_orders", 0) >= 1, "Manager summary must include pending orders")
    expect(summary.get("top_dish_today"), "Manager summary must include top_dish_today")

    staff_summary = api_get(base_url, "/analytics/summary", token=staff_token, query={"point_id": ids["point_id"]})
    expect(isinstance(staff_summary, dict) and staff_summary.get("total_orders_today", 0) >= 1, "Staff summary must be accessible and populated")

    forecast = api_get(base_url, "/analytics/forecast", token=manager_token, query={"point_id": ids["point_id"], "horizon_days": 7, "lookback_days": 28})
    expect(isinstance(forecast, dict) and len(forecast.get("items", [])) >= 1, "Forecast must contain purchase recommendations")

    anomalies = api_get(base_url, "/analytics/anomalies", token=manager_token, query={"point_id": ids["point_id"], "limit": 5})
    expect(isinstance(anomalies, dict) and len(anomalies.get("signals", [])) >= 1, "Anomalies must contain at least one signal")

    assistant = api_post(base_url, "/analytics/assistant/chat", {"question": "Что важно показать в демо сегодня?", "point_id": ids["point_id"]}, token=admin_token)
    expect(isinstance(assistant, dict) and len(assistant.get("evidence", [])) >= 1, "Assistant response must include evidence")

    ingredients = api_get(base_url, "/warehouse/ingredients", token=manager_token)
    expect(isinstance(ingredients, list) and len(ingredients) >= 8, "Warehouse ingredients must include demo ingredients")

    warehouse_dishes = api_get(base_url, "/warehouse/dishes", token=manager_token)
    expect(isinstance(warehouse_dishes, list) and len(warehouse_dishes) >= 6, "Warehouse dishes must include demo dishes")

    stock = api_get(base_url, "/warehouse/stock", token=manager_token, query={"point_id": ids["point_id"]})
    expect(isinstance(stock, list) and len(stock) >= 8, "Warehouse stock must be populated")

    movements = api_get(base_url, "/warehouse/stock/movements", token=manager_token, query={"point_id": ids["point_id"], "limit": 10})
    expect(isinstance(movements, list) and len(movements) >= 3, "Warehouse movements must be populated")

    audit = api_get(base_url, "/warehouse/audit", token=manager_token, query={"point_id": ids["point_id"], "limit": 10})
    expect(isinstance(audit, list) and len(audit) >= 3, "Warehouse audit must be populated")

    franchisee_list = api_get(base_url, "/franchisees", token=admin_token)
    expect(isinstance(franchisee_list, list) and len(franchisee_list) >= 3, "Admin franchisee list must include demo franchisees")

    franchisee_card = api_get(base_url, f"/franchisees/{ids['franchisee_id']}", token=franchisee_token)
    expect(isinstance(franchisee_card, dict) and franchisee_card.get("id") == ids["franchisee_id"], "Franchisee card must be accessible to owner")

    franchisee_tasks = api_get(base_url, f"/franchisees/{ids['franchisee_id']}/tasks", token=franchisee_token)
    expect(isinstance(franchisee_tasks, dict) and len(franchisee_tasks.get("tasks", [])) >= 1, "Franchisee tasks route must be populated")

    franchisee_notes = api_get(base_url, f"/franchisees/{ids['franchisee_id']}/notes", token=franchisee_token)
    expect(isinstance(franchisee_notes, list) and len(franchisee_notes) >= 1, "Franchisee notes route must be populated")

    franchisee_points_payload = api_get(base_url, f"/franchisees/{ids['franchisee_id']}/points", token=franchisee_token)
    expect(isinstance(franchisee_points_payload, list) and len(franchisee_points_payload) >= 2, "Franchisee points route must be populated")


async def main_async(args: argparse.Namespace) -> None:
    async with SessionLocal() as db:
        state = await load_demo_state(db)
        await verify_cleanup_safety(db)
        tokens = await verify_logins(db)

    base_url = detect_base_url(args.base_url)

    main_franchisee = state["main_franchisee"]
    points_by_name = state["points_by_name"]
    ids = {
        "point_id": str(points_by_name[f"{DEMO_PREFIX} Ufa 1"].id),
        "franchisee_id": str(main_franchisee.id),
    }
    verify_api(base_url, tokens, ids)

    print("Demo seed verification passed.")
    print(f"Base URL: {base_url}")
    print(f"Users: {len(state['users_by_email'])}")
    print(f"Points: {len(state['points'])}")
    print(f"Franchisees: {len(state['franchisees'])}")
    print(f"Orders: {len(state['orders'])}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Verify deterministic demo seed data and routes.")
    parser.add_argument(
        "--base-url",
        help="Optional API base URL, for example http://127.0.0.1:18000/api/v1",
    )
    return parser.parse_args()


def main() -> None:
    asyncio.run(main_async(parse_args()))


if __name__ == "__main__":
    main()
