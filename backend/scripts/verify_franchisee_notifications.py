from __future__ import annotations

import asyncio
import sys
import uuid
from datetime import date, datetime, timedelta, timezone

import bcrypt

sys.path.insert(0, "/workspace")

import backend.app.models.franchisee  # noqa: F401
import backend.app.models.franchisee_task  # noqa: F401
import backend.app.models.user  # noqa: F401
from backend.app.db.session import SessionLocal
from backend.app.models.franchisee import Franchisee, FranchiseeStatus
from backend.app.models.franchisee_task import FranchiseeTask, TaskStatus
from backend.app.models.user import User, UserRole
from backend.app.tasks.notifications import (
    send_franchisee_stage_notification,
    send_franchisee_task_status_notification,
    send_overdue_franchisee_task_notifications,
)

CHAT_ID = "700800900"


def _hash(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


async def seed() -> tuple[str, str]:
    suffix = uuid.uuid4().hex[:6]
    async with SessionLocal() as db:
        owner = User(
            email=f"fr-owner-{suffix}@japonica.example.com",
            password_hash=_hash("Owner1234!"),
            name="Responsible Owner",
            role=UserRole.SUPER_ADMIN,
            telegram_chat_id=CHAT_ID,
            notification_settings={
                "franchisee_stage_changed": True,
                "franchisee_task_changed": True,
                "franchisee_task_overdue": True,
            },
            is_active=True,
        )
        franchisee = Franchisee(
            company_name=f"Notify Franchisee {suffix}",
            contact_name="Ivan Petrov",
            status=FranchiseeStatus.NEGOTIATION,
            responsible_owner_id=None,
        )
        db.add(owner)
        await db.flush()
        franchisee.responsible_owner_id = owner.id
        db.add(franchisee)
        await db.flush()

        task = FranchiseeTask(
            franchisee_id=franchisee.id,
            title="Подписать договор",
            stage=FranchiseeStatus.NEGOTIATION,
            status=TaskStatus.IN_PROGRESS,
            due_date=date.today() - timedelta(days=1),
            created_at=datetime.now(timezone.utc),
            completed_at=None,
        )
        db.add(task)
        await db.commit()
        return str(franchisee.id), str(task.id)


def main() -> None:
    franchisee_id, task_id = asyncio.run(seed())

    stage_result = send_franchisee_stage_notification.delay(franchisee_id, "contract").get(
        timeout=30
    )
    assert stage_result["status"] == "sent", stage_result
    assert any(item["chat_id"] == CHAT_ID for item in stage_result["recipients"]), stage_result

    task_result = send_franchisee_task_status_notification.delay(
        franchisee_id,
        task_id,
        "done",
    ).get(timeout=30)
    assert task_result["status"] == "sent", task_result
    assert any(item["chat_id"] == CHAT_ID for item in task_result["recipients"]), task_result

    overdue_first = send_overdue_franchisee_task_notifications.delay().get(timeout=30)
    overdue_first_recipients = overdue_first.get("recipients", [])
    assert any(item["chat_id"] == CHAT_ID for item in overdue_first_recipients), overdue_first

    overdue_second = send_overdue_franchisee_task_notifications.delay().get(timeout=30)
    overdue_second_recipients = overdue_second.get("recipients", [])
    assert all(item["chat_id"] != CHAT_ID for item in overdue_second_recipients), overdue_second

    print("PASS: franchisee stage/task/overdue notifications resolve the responsible owner")


if __name__ == "__main__":
    main()
