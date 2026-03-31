from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.franchisee import Franchisee, FranchiseeStatus
from backend.app.models.franchisee_task import FranchiseeTask, TaskStatus
from backend.app.models.point import Point
from backend.app.models.user import User, UserRole
from backend.app.models.user_point import UserPoint
from backend.app.modules.franchisee.schemas import (
    FranchiseeCreate,
    FranchiseePointAttachRequest,
    FranchiseeUpdate,
    NoteCreate,
    TaskCreate,
)


async def create_franchisee(db: AsyncSession, data: FranchiseeCreate) -> Franchisee:
    franchisee = Franchisee(
        company_name=data.company_name,
        contact_name=data.contact_name,
        contact_email=data.contact_email,
        contact_phone=data.contact_phone,
        responsible_owner_id=data.responsible_owner_id,
        status=FranchiseeStatus.LEAD,
    )
    db.add(franchisee)
    await db.commit()
    await db.refresh(franchisee)
    return franchisee


async def list_franchisees(
    db: AsyncSession,
    status: FranchiseeStatus | None = None,
) -> list:
    points_subq = (
        select(Point.franchisee_id, func.count(Point.id).label("points_count"))
        .where(Point.franchisee_id.is_not(None))
        .group_by(Point.franchisee_id)
        .subquery()
    )

    query = select(
        Franchisee, func.coalesce(points_subq.c.points_count, 0).label("points_count")
    ).outerjoin(points_subq, points_subq.c.franchisee_id == Franchisee.id)

    if status is not None:
        query = query.where(Franchisee.status == status)

    result = await db.execute(query)
    return result.all()


async def get_franchisee_with_points_count(
    db: AsyncSession, franchisee_id: uuid.UUID
) -> tuple | None:
    points_subq = (
        select(Point.franchisee_id, func.count(Point.id).label("points_count"))
        .where(Point.franchisee_id.is_not(None))
        .group_by(Point.franchisee_id)
        .subquery()
    )

    result = await db.execute(
        select(
            Franchisee, func.coalesce(points_subq.c.points_count, 0).label("points_count")
        )
        .outerjoin(points_subq, points_subq.c.franchisee_id == Franchisee.id)
        .where(Franchisee.id == franchisee_id)
    )
    row = result.first()
    return row if row else None


async def get_franchisee_ids_for_user(db: AsyncSession, user_id: uuid.UUID) -> list[uuid.UUID]:
    """Return franchisee IDs owned by the user or reachable through their points."""
    result = await db.execute(
        select(Franchisee.id).where(Franchisee.responsible_owner_id == user_id)
    )
    franchisee_ids = {row[0] for row in result.all()}

    result = await db.execute(
        select(Point.franchisee_id)
        .join(UserPoint, UserPoint.point_id == Point.id)
        .where(
            UserPoint.user_id == user_id,
            Point.franchisee_id.is_not(None),
        )
    )
    franchisee_ids.update(row[0] for row in result.all() if row[0] is not None)
    return list(franchisee_ids)


async def get_accessible_franchisee_ids_for_user(
    db: AsyncSession, user_id: uuid.UUID
) -> list[uuid.UUID]:
    return await get_franchisee_ids_for_user(db, user_id)


async def get_accessible_points_for_user(db: AsyncSession, user: User) -> list[Point]:
    if user.role == UserRole.SUPER_ADMIN:
        result = await db.execute(select(Point).order_by(Point.name))
        return list(result.scalars().all())

    conditions = []

    result = await db.execute(select(UserPoint.point_id).where(UserPoint.user_id == user.id))
    point_ids = [row[0] for row in result.all()]
    if point_ids:
        conditions.append(Point.id.in_(point_ids))

    if user.role == UserRole.FRANCHISEE:
        franchisee_ids = await get_franchisee_ids_for_user(db, user.id)
        if franchisee_ids:
            conditions.append(Point.franchisee_id.in_(franchisee_ids))

    if not conditions:
        return []

    point_ids_subquery = (
        select(Point.id)
        .where(or_(*conditions))
        .distinct()
        .subquery()
    )

    result = await db.execute(
        select(Point)
        .where(Point.id.in_(select(point_ids_subquery.c.id)))
        .order_by(Point.name)
    )
    return list(result.scalars().all())


async def get_accessible_point_ids_for_user(db: AsyncSession, user: User) -> list[uuid.UUID]:
    points = await get_accessible_points_for_user(db, user)
    return [point.id for point in points]


async def update_franchisee(
    db: AsyncSession, franchisee: Franchisee, data: FranchiseeUpdate
) -> Franchisee:
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(franchisee, field, value)
    await db.commit()
    await db.refresh(franchisee)
    return franchisee


async def update_franchisee_stage(
    db: AsyncSession, franchisee: Franchisee, new_status: FranchiseeStatus
) -> Franchisee:
    franchisee.status = new_status
    await db.commit()
    await db.refresh(franchisee)
    return franchisee


async def get_tasks_for_franchisee(
    db: AsyncSession, franchisee_id: uuid.UUID
) -> list[FranchiseeTask]:
    result = await db.execute(
        select(FranchiseeTask).where(FranchiseeTask.franchisee_id == franchisee_id)
    )
    return list(result.scalars().all())


async def create_task(
    db: AsyncSession, franchisee_id: uuid.UUID, data: TaskCreate
) -> FranchiseeTask:
    task = FranchiseeTask(
        franchisee_id=franchisee_id,
        title=data.title,
        stage=data.stage,
        status=TaskStatus.PENDING,
        due_date=data.due_date,
        created_at=datetime.now(timezone.utc),
    )
    db.add(task)
    await db.commit()
    await db.refresh(task)
    return task


async def update_task_status(
    db: AsyncSession, task: FranchiseeTask, new_status: TaskStatus
) -> FranchiseeTask:
    task.status = new_status
    if new_status == TaskStatus.DONE:
        task.completed_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(task)
    return task


def _parse_notes(raw_notes: str | None) -> list[dict]:
    if not raw_notes:
        return []
    try:
        parsed = json.loads(raw_notes)
        if isinstance(parsed, list):
            return parsed
    except json.JSONDecodeError:
        pass

    return [
        {
            "id": str(uuid.uuid4()),
            "text": raw_notes,
            "author": None,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
    ]


async def list_notes(db: AsyncSession, franchisee: Franchisee) -> list[dict]:
    return _parse_notes(franchisee.notes)


async def add_note(
    db: AsyncSession,
    franchisee: Franchisee,
    data: NoteCreate,
    fallback_author: str,
) -> list[dict]:
    notes = _parse_notes(franchisee.notes)
    notes.append(
        {
            "id": str(uuid.uuid4()),
            "text": data.text,
            "author": data.author or fallback_author,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
    )
    franchisee.notes = json.dumps(notes, ensure_ascii=False)
    await db.commit()
    await db.refresh(franchisee)
    return notes


async def list_points_for_franchisee(
    db: AsyncSession,
    franchisee_id: uuid.UUID,
) -> list[Point]:
    result = await db.execute(
        select(Point)
        .where(Point.franchisee_id == franchisee_id)
        .order_by(Point.name)
    )
    return list(result.scalars().all())


async def attach_point(
    db: AsyncSession,
    franchisee_id: uuid.UUID,
    data: FranchiseePointAttachRequest,
) -> Point:
    if data.point_id is not None:
        result = await db.execute(select(Point).where(Point.id == data.point_id))
        point = result.scalar_one_or_none()
        if point is None:
            raise ValueError("Point not found")
    else:
        point = Point(
            franchisee_id=franchisee_id,
            name=data.name or "",
            address=data.address or "",
        )
        db.add(point)
        await db.flush()

    point.franchisee_id = franchisee_id
    await db.commit()
    await db.refresh(point)
    return point


async def detach_point(
    db: AsyncSession,
    franchisee_id: uuid.UUID,
    point_id: uuid.UUID,
) -> None:
    result = await db.execute(
        select(Point).where(Point.id == point_id, Point.franchisee_id == franchisee_id)
    )
    point = result.scalar_one_or_none()
    if point is None:
        raise ValueError("Point not found")
    point.franchisee_id = None
    await db.commit()
