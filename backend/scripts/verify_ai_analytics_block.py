from __future__ import annotations

import asyncio
import json
import sys
import uuid
import urllib.request
from datetime import UTC, datetime, timedelta
from decimal import Decimal

sys.path.insert(0, "/workspace")

import backend.app.models.dish  # noqa: F401
import backend.app.models.dish_ingredient  # noqa: F401
import backend.app.models.franchisee  # noqa: F401
import backend.app.models.franchisee_task  # noqa: F401
import backend.app.models.ingredient  # noqa: F401
import backend.app.models.order  # noqa: F401
import backend.app.models.point  # noqa: F401
import backend.app.models.stock_item  # noqa: F401
import backend.app.models.stock_movement  # noqa: F401
import backend.app.models.user_point  # noqa: F401
from sqlalchemy import select

from backend.app.db.session import SessionLocal
from backend.app.models.dish import Dish
from backend.app.models.dish_ingredient import DishIngredient
from backend.app.models.ingredient import Ingredient
from backend.app.models.order import Order, OrderStatus, PaymentStatus, PaymentType, SourceChannel
from backend.app.models.point import Point
from backend.app.models.stock_item import StockItem
from backend.app.models.stock_movement import MovementType, StockMovement

BASE_URL = "http://127.0.0.1:8000/api/v1"
ADMIN_EMAIL = "admin@japonica.example.com"
ADMIN_PASSWORD = "Admin1234!"


def http_post(url: str, data: dict, headers: dict[str, str] | None = None) -> dict:
    body = json.dumps(data).encode()
    req = urllib.request.Request(url, data=body, method="POST")
    req.add_header("Content-Type", "application/json")
    if headers:
        for key, value in headers.items():
            req.add_header(key, value)
    with urllib.request.urlopen(req) as response:
        return json.loads(response.read())


def http_get(url: str, headers: dict[str, str] | None = None):
    req = urllib.request.Request(url, method="GET")
    if headers:
        for key, value in headers.items():
            req.add_header(key, value)
    with urllib.request.urlopen(req) as response:
        return json.loads(response.read())


async def seed() -> str:
    suffix = uuid.uuid4().hex[:6]

    async with SessionLocal() as db:
        point = Point(
            name=f"AI Point {suffix}",
            address="Analytics street",
            payment_types=[],
            is_active=True,
        )
        db.add(point)
        await db.flush()

        ingredient = Ingredient(
            name=f"AI Rice {suffix}",
            unit="kg",
            min_stock_level=Decimal("5.000"),
            is_active=True,
        )
        dish = Dish(
            name=f"AI Roll {suffix}",
            description="Verification dish",
            price=Decimal("350.00"),
            is_active=True,
        )
        db.add_all([ingredient, dish])
        await db.flush()

        db.add(
            DishIngredient(
                dish_id=dish.id,
                ingredient_id=ingredient.id,
                quantity_per_portion=Decimal("0.080"),
            )
        )
        stock_item = StockItem(
            ingredient_id=ingredient.id,
            point_id=point.id,
            quantity=Decimal("2.000"),
        )
        db.add(stock_item)
        await db.flush()

        old_created_at = datetime.now(UTC) - timedelta(days=10)
        recent_order_created_at = datetime.now(UTC) - timedelta(days=2)
        recent_movement_created_at = datetime.now(UTC) - timedelta(days=1)

        for _ in range(6):
            db.add(
                Order(
                    point_id=point.id,
                    status=OrderStatus.DELIVERED,
                    payment_type=PaymentType.CARD,
                    payment_status=PaymentStatus.PAID,
                    source_channel=SourceChannel.POS,
                    items=[
                        {
                            "dish_id": str(dish.id),
                            "name": dish.name,
                            "quantity": 2,
                            "price": "350.00",
                        }
                    ],
                    total_amount=Decimal("700.00"),
                    notes="analytics baseline",
                    created_at=old_created_at,
                    updated_at=old_created_at,
                )
            )

        db.add(
            Order(
                point_id=point.id,
                status=OrderStatus.DELIVERED,
                payment_type=PaymentType.CASH,
                payment_status=PaymentStatus.PAID,
                source_channel=SourceChannel.WEBSITE,
                items=[
                    {
                        "dish_id": str(dish.id),
                        "name": dish.name,
                        "quantity": 1,
                        "price": "350.00",
                    }
                ],
                total_amount=Decimal("350.00"),
                notes="analytics recent",
                created_at=recent_order_created_at,
                updated_at=recent_order_created_at,
            )
        )
        db.add(
            StockMovement(
                stock_item_id=stock_item.id,
                movement_type=MovementType.OUT,
                quantity=Decimal("20.000"),
                reason="variance-check",
                created_by_id=None,
                created_at=recent_movement_created_at,
            )
        )
        await db.commit()
        return str(point.id)


def main() -> None:
    point_id = asyncio.run(seed())
    token = http_post(
        f"{BASE_URL}/auth/login",
        {"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
    )["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    assistant = http_post(
        f"{BASE_URL}/analytics/assistant/chat",
        {
            "question": "What anomalies need attention and what should we buy next week?",
            "point_id": point_id,
        },
        headers=headers,
    )
    forecast = http_get(
        f"{BASE_URL}/analytics/forecast?point_id={point_id}&horizon_days=7&lookback_days=28",
        headers=headers,
    )
    anomalies = http_get(
        f"{BASE_URL}/analytics/anomalies?point_id={point_id}&limit=10",
        headers=headers,
    )

    assert assistant["context_scope"]
    assert assistant["evidence"], assistant
    assert "provider" in assistant
    assert any(char.isdigit() for char in assistant["answer"]) or "₽" in assistant["answer"]

    assert forecast["items"], forecast
    assert Decimal(forecast["items"][0]["recommended_purchase"]) > 0, forecast

    anomaly_types = {item["type"] for item in anomalies["signals"]}
    assert "sales_drop" in anomaly_types, anomalies
    assert "suspicious_writeoff" in anomaly_types, anomalies

    print("PASS: assistant, forecast, and anomalies endpoints return evidence-backed analytics")


if __name__ == "__main__":
    main()
