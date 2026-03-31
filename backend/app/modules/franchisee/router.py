from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.deps import require_franchisee_or_above, require_super_admin
from backend.app.db.session import get_db_session
from backend.app.models.franchisee import Franchisee, FranchiseeStatus
from backend.app.models.franchisee_task import FranchiseeTask, TaskStatus
from backend.app.models.user import User, UserRole
from backend.app.modules.franchisee import schemas as s
from backend.app.modules.franchisee import service

router = APIRouter(prefix="/franchisees", tags=["franchisee"])


# ── helpers ──────────────────────────────────────────────────────────────────

async def _get_franchisee_or_404(
    franchisee_id: uuid.UUID, db: AsyncSession
) -> Franchisee:
    result = await db.execute(select(Franchisee).where(Franchisee.id == franchisee_id))
    franchisee = result.scalar_one_or_none()
    if franchisee is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Franchisee not found")
    return franchisee


async def _get_task_or_404(
    task_id: uuid.UUID, franchisee_id: uuid.UUID, db: AsyncSession
) -> FranchiseeTask:
    result = await db.execute(
        select(FranchiseeTask).where(
            FranchiseeTask.id == task_id,
            FranchiseeTask.franchisee_id == franchisee_id,
        )
    )
    task = result.scalar_one_or_none()
    if task is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    return task


def _compute_stage_progress(
    tasks: list[FranchiseeTask], current_stage: FranchiseeStatus
) -> s.StageProgress:
    tasks_for_stage = [t for t in tasks if t.stage == current_stage]
    total = len(tasks_for_stage)
    done = len([t for t in tasks_for_stage if t.status == TaskStatus.DONE])
    percent = int(done / total * 100) if total > 0 else 0
    return s.StageProgress(
        stage=current_stage.value,
        total=total,
        done=done,
        percent=percent,
    )


def _franchisee_to_response(franchisee: Franchisee, points_count: int) -> s.FranchiseeResponse:
    return s.FranchiseeResponse(
        id=franchisee.id,
        company_name=franchisee.company_name,
        contact_name=franchisee.contact_name,
        contact_email=franchisee.contact_email,
        contact_phone=franchisee.contact_phone,
        status=franchisee.status,
        responsible_owner_id=franchisee.responsible_owner_id,
        notes=franchisee.notes,
        created_at=franchisee.created_at,
        updated_at=franchisee.updated_at,
        points_count=points_count,
    )


# ── TASK-025 endpoints ───────────────────────────────────────────────────────

@router.post("", response_model=s.FranchiseeResponse, status_code=status.HTTP_201_CREATED)
async def create_franchisee(
    data: s.FranchiseeCreate,
    user: User = Depends(require_super_admin),
    db: AsyncSession = Depends(get_db_session),
) -> s.FranchiseeResponse:
    franchisee = await service.create_franchisee(db, data)
    return _franchisee_to_response(franchisee, 0)


@router.get("", response_model=list[s.FranchiseeResponse])
async def list_franchisees(
    status_filter: FranchiseeStatus | None = None,
    user: User = Depends(require_super_admin),
    db: AsyncSession = Depends(get_db_session),
) -> list[s.FranchiseeResponse]:
    rows = await service.list_franchisees(db, status=status_filter)
    return [_franchisee_to_response(f, pc) for f, pc in rows]


@router.get("/{franchisee_id}", response_model=s.FranchiseeResponse)
async def get_franchisee(
    franchisee_id: uuid.UUID,
    user: User = Depends(require_franchisee_or_above),
    db: AsyncSession = Depends(get_db_session),
) -> s.FranchiseeResponse:
    # Franchisee role can only see their own card
    if user.role == UserRole.FRANCHISEE:
        allowed_ids = await service.get_franchisee_ids_for_user(db, user.id)
        if franchisee_id not in allowed_ids:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")

    row = await service.get_franchisee_with_points_count(db, franchisee_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Franchisee not found")
    franchisee, points_count = row
    return _franchisee_to_response(franchisee, points_count)


@router.patch("/{franchisee_id}", response_model=s.FranchiseeResponse)
async def update_franchisee(
    franchisee_id: uuid.UUID,
    data: s.FranchiseeUpdate,
    user: User = Depends(require_super_admin),
    db: AsyncSession = Depends(get_db_session),
) -> s.FranchiseeResponse:
    franchisee = await _get_franchisee_or_404(franchisee_id, db)
    franchisee = await service.update_franchisee(db, franchisee, data)
    row = await service.get_franchisee_with_points_count(db, franchisee_id)
    _, points_count = row if row else (None, 0)
    return _franchisee_to_response(franchisee, points_count)


# ── TASK-026 endpoints ───────────────────────────────────────────────────────

@router.patch("/{franchisee_id}/stage", response_model=s.StageResponse)
async def update_stage(
    franchisee_id: uuid.UUID,
    data: s.StageUpdate,
    user: User = Depends(require_super_admin),
    db: AsyncSession = Depends(get_db_session),
) -> s.StageResponse:
    franchisee = await _get_franchisee_or_404(franchisee_id, db)
    previous_status = franchisee.status
    franchisee = await service.update_franchisee_stage(db, franchisee, data.status)
    if previous_status != franchisee.status:
        from backend.app.tasks.notifications import send_franchisee_stage_notification

        send_franchisee_stage_notification.delay(
            franchisee_id=str(franchisee.id),
            new_status=franchisee.status.value,
        )
    tasks = await service.get_tasks_for_franchisee(db, franchisee_id)
    progress = _compute_stage_progress(tasks, franchisee.status)
    return s.StageResponse(
        id=franchisee.id,
        status=franchisee.status,
        progress=progress.model_dump(),
    )


@router.get("/{franchisee_id}/tasks", response_model=s.TaskListResponse)
async def list_tasks(
    franchisee_id: uuid.UUID,
    user: User = Depends(require_franchisee_or_above),
    db: AsyncSession = Depends(get_db_session),
) -> s.TaskListResponse:
    # Franchisee role can only see tasks for their own franchisee
    if user.role == UserRole.FRANCHISEE:
        allowed_ids = await service.get_franchisee_ids_for_user(db, user.id)
        if franchisee_id not in allowed_ids:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")

    franchisee = await _get_franchisee_or_404(franchisee_id, db)
    tasks = await service.get_tasks_for_franchisee(db, franchisee_id)
    progress = _compute_stage_progress(tasks, franchisee.status)
    task_responses = [s.TaskResponse.model_validate(t) for t in tasks]
    return s.TaskListResponse(tasks=task_responses, stage_progress=progress)


@router.post(
    "/{franchisee_id}/tasks",
    response_model=s.TaskResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_task(
    franchisee_id: uuid.UUID,
    data: s.TaskCreate,
    user: User = Depends(require_super_admin),
    db: AsyncSession = Depends(get_db_session),
) -> s.TaskResponse:
    await _get_franchisee_or_404(franchisee_id, db)
    task = await service.create_task(db, franchisee_id, data)
    return s.TaskResponse.model_validate(task)


@router.patch("/{franchisee_id}/tasks/{task_id}", response_model=s.TaskResponse)
async def update_task(
    franchisee_id: uuid.UUID,
    task_id: uuid.UUID,
    data: s.TaskStatusUpdate,
    user: User = Depends(require_franchisee_or_above),
    db: AsyncSession = Depends(get_db_session),
) -> s.TaskResponse:
    # Franchisee role can only update tasks for their own franchisee
    if user.role == UserRole.FRANCHISEE:
        allowed_ids = await service.get_franchisee_ids_for_user(db, user.id)
        if franchisee_id not in allowed_ids:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")

    task = await _get_task_or_404(task_id, franchisee_id, db)
    previous_status = task.status
    task = await service.update_task_status(db, task, data.status)
    if previous_status != task.status:
        from backend.app.tasks.notifications import send_franchisee_task_status_notification

        send_franchisee_task_status_notification.delay(
            franchisee_id=str(franchisee_id),
            task_id=str(task.id),
            new_status=task.status.value,
        )
    return s.TaskResponse.model_validate(task)


# ── TASK-028 endpoints ───────────────────────────────────────────────────────

@router.get("/{franchisee_id}/notes", response_model=list[s.NoteResponse])
async def list_notes(
    franchisee_id: uuid.UUID,
    user: User = Depends(require_franchisee_or_above),
    db: AsyncSession = Depends(get_db_session),
) -> list[s.NoteResponse]:
    if user.role == UserRole.FRANCHISEE:
        allowed_ids = await service.get_franchisee_ids_for_user(db, user.id)
        if franchisee_id not in allowed_ids:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")

    franchisee = await _get_franchisee_or_404(franchisee_id, db)
    notes = await service.list_notes(db, franchisee)
    return [s.NoteResponse.model_validate(note) for note in notes]


@router.post("/{franchisee_id}/notes", response_model=list[s.NoteResponse])
async def add_note(
    franchisee_id: uuid.UUID,
    data: s.NoteCreate,
    user: User = Depends(require_super_admin),
    db: AsyncSession = Depends(get_db_session),
) -> list[s.NoteResponse]:
    franchisee = await _get_franchisee_or_404(franchisee_id, db)
    notes = await service.add_note(db, franchisee, data, fallback_author=user.name)
    return [s.NoteResponse.model_validate(note) for note in notes]


# ── TASK-029 endpoints ───────────────────────────────────────────────────────

@router.get("/{franchisee_id}/points", response_model=list[s.FranchiseePointResponse])
async def list_franchisee_points(
    franchisee_id: uuid.UUID,
    user: User = Depends(require_franchisee_or_above),
    db: AsyncSession = Depends(get_db_session),
) -> list[s.FranchiseePointResponse]:
    if user.role == UserRole.FRANCHISEE:
        allowed_ids = await service.get_franchisee_ids_for_user(db, user.id)
        if franchisee_id not in allowed_ids:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")

    await _get_franchisee_or_404(franchisee_id, db)
    points = await service.list_points_for_franchisee(db, franchisee_id)
    return [s.FranchiseePointResponse.model_validate(point) for point in points]


@router.post(
    "/{franchisee_id}/points",
    response_model=s.FranchiseePointResponse,
    status_code=status.HTTP_201_CREATED,
)
async def attach_franchisee_point(
    franchisee_id: uuid.UUID,
    data: s.FranchiseePointAttachRequest,
    user: User = Depends(require_super_admin),
    db: AsyncSession = Depends(get_db_session),
) -> s.FranchiseePointResponse:
    await _get_franchisee_or_404(franchisee_id, db)
    try:
        point = await service.attach_point(db, franchisee_id, data)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    return s.FranchiseePointResponse.model_validate(point)


@router.delete(
    "/{franchisee_id}/points/{point_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def detach_franchisee_point(
    franchisee_id: uuid.UUID,
    point_id: uuid.UUID,
    user: User = Depends(require_super_admin),
    db: AsyncSession = Depends(get_db_session),
) -> None:
    await _get_franchisee_or_404(franchisee_id, db)
    try:
        await service.detach_point(db, franchisee_id, point_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
