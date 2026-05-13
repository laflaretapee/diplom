from __future__ import annotations

import asyncio
import sys

sys.path.insert(0, "/workspace")

from sqlalchemy import select

import backend.app.models.franchisee  # noqa: F401
import backend.app.models.franchisee_task  # noqa: F401
import backend.app.models.user  # noqa: F401
import backend.app.models.user_point  # noqa: F401
from backend.app.db.session import SessionLocal
from backend.app.models.user import User
from backend.app.tasks.notifications import send_weekly_revenue_report

ADMIN_EMAIL = "admin@japonica.example.com"
CHAT_ID = "777888999"


async def seed() -> None:
    async with SessionLocal() as db:
        admin = (
            await db.execute(select(User).where(User.email == ADMIN_EMAIL))
        ).scalar_one_or_none()
        if admin is None:
            raise RuntimeError("Admin user not found for weekly report verification")
        admin.telegram_chat_id = CHAT_ID
        settings = (
            admin.notification_settings
            if isinstance(admin.notification_settings, dict)
            else {}
        )
        settings["weekly_revenue_report"] = True
        admin.notification_settings = settings
        await db.commit()


def main() -> None:
    asyncio.run(seed())
    result = send_weekly_revenue_report.delay().get(timeout=30)
    assert result["status"] == "sent", result
    assert result["count"] >= 1, result
    assert any(item["chat_id"] == CHAT_ID for item in result["recipients"]), result
    print("PASS: weekly revenue report resolves recipients and dispatches through Celery")


if __name__ == "__main__":
    main()
