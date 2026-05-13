"""
TASK-030 verification: Telegram account linking flow.
"""
from __future__ import annotations

import asyncio
import json
import sys
import urllib.error
import urllib.request

sys.path.insert(0, "/workspace")

from sqlalchemy import select

import backend.app.models.franchisee  # noqa: F401
import backend.app.models.franchisee_task  # noqa: F401
import backend.app.models.user_point  # noqa: F401
from backend.app.core.config import get_settings
from backend.app.db.session import SessionLocal
from backend.app.models.user import User

BASE_URL = "http://127.0.0.1:8000/api/v1"
ADMIN_EMAIL = "admin@japonica.example.com"
ADMIN_PASSWORD = "Admin1234!"


def http_post(
    url: str,
    data: dict,
    headers: dict[str, str] | None = None,
) -> dict:
    body = json.dumps(data).encode()
    req = urllib.request.Request(url, data=body, method="POST")
    req.add_header("Content-Type", "application/json")
    if headers:
        for key, value in headers.items():
            req.add_header(key, value)
    with urllib.request.urlopen(req) as response:
        return json.loads(response.read())


def http_get(url: str, headers: dict[str, str] | None = None) -> dict:
    req = urllib.request.Request(url, method="GET")
    if headers:
        for key, value in headers.items():
            req.add_header(key, value)
    with urllib.request.urlopen(req) as response:
        return json.loads(response.read())


async def reset_admin_chat_id() -> None:
    async with SessionLocal() as db:
        result = await db.execute(select(User).where(User.email == ADMIN_EMAIL))
        user = result.scalar_one_or_none()
        if user is None:
            raise RuntimeError("Admin user not found. Seed admin first.")
        user.telegram_chat_id = None
        await db.commit()


def main() -> None:
    asyncio.run(reset_admin_chat_id())

    login = http_post(
        f"{BASE_URL}/auth/login",
        {"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
    )
    token = login["access_token"]
    auth_headers = {"Authorization": f"Bearer {token}"}

    status_before = http_get(
        f"{BASE_URL}/notifications/telegram/status",
        headers=auth_headers,
    )
    assert status_before == {"linked": False, "chat_id": None}

    link = http_post(
        f"{BASE_URL}/notifications/telegram/link",
        {},
        headers=auth_headers,
    )
    assert len(link["code"]) == 6

    webhook_payload = {
        "message": {
            "text": f"/link {link['code']}",
            "chat": {"id": 123456789},
        }
    }
    webhook_headers = {
        "X-Telegram-Bot-Api-Secret-Token": get_settings().telegram_webhook_secret,
    }
    webhook = http_post(
        f"{BASE_URL}/notifications/telegram/webhook",
        webhook_payload,
        headers=webhook_headers,
    )
    assert webhook["ok"] is True

    status_after = http_get(
        f"{BASE_URL}/notifications/telegram/status",
        headers=auth_headers,
    )
    assert status_after == {"linked": True, "chat_id": "123456789"}

    unlink = http_post(
        f"{BASE_URL}/notifications/telegram/unlink",
        {},
        headers=auth_headers,
    )
    assert unlink["ok"] is True

    status_final = http_get(
        f"{BASE_URL}/notifications/telegram/status",
        headers=auth_headers,
    )
    assert status_final == {"linked": False, "chat_id": None}

    print("SUCCESS: telegram linking flow works end-to-end.")


if __name__ == "__main__":
    main()
