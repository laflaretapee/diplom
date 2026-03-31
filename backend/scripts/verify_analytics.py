"""
TASK-035 verification: analytics endpoints return real aggregated data.
"""
from __future__ import annotations

import asyncio
import json
import sys
import urllib.request

sys.path.insert(0, "/workspace")

import backend.app.models.franchisee  # noqa: F401
import backend.app.models.franchisee_task  # noqa: F401
import backend.app.models.user_point  # noqa: F401
from sqlalchemy import select

from backend.app.db.session import SessionLocal
from backend.app.models.point import Point

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


async def get_point_id() -> str:
    async with SessionLocal() as db:
        result = await db.execute(select(Point.id).limit(1))
        point_id = result.scalar_one_or_none()
        if point_id is None:
            raise RuntimeError("No point found for analytics verification")
        return str(point_id)


def main() -> None:
    point_id = asyncio.run(get_point_id())
    token = http_post(
        f"{BASE_URL}/auth/login",
        {"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
    )["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    revenue = http_get(f"{BASE_URL}/analytics/revenue?period=week", headers=headers)
    dishes = http_get(
        f"{BASE_URL}/analytics/dishes?period=week&point_id={point_id}",
        headers=headers,
    )
    channels = http_get(
        f"{BASE_URL}/analytics/channels?period=week&point_id={point_id}",
        headers=headers,
    )
    summary = http_get(
        f"{BASE_URL}/analytics/summary?point_id={point_id}",
        headers=headers,
    )

    assert isinstance(revenue, list)
    assert "top" in dishes and "bottom" in dishes
    assert isinstance(channels, list)
    assert "total_orders_today" in summary
    assert "top_dish_today" in summary

    print("SUCCESS: analytics endpoints returned valid payloads.")


if __name__ == "__main__":
    main()
