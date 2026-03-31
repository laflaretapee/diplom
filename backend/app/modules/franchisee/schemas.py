from __future__ import annotations

import uuid
from datetime import date, datetime

from pydantic import BaseModel, model_validator

from backend.app.models.franchisee import FranchiseeStatus
from backend.app.models.franchisee_task import TaskStatus


class FranchiseeCreate(BaseModel):
    company_name: str
    contact_name: str | None = None
    contact_email: str | None = None
    contact_phone: str | None = None
    responsible_owner_id: uuid.UUID | None = None


class FranchiseeUpdate(BaseModel):
    company_name: str | None = None
    contact_name: str | None = None
    contact_email: str | None = None
    contact_phone: str | None = None
    status: FranchiseeStatus | None = None
    responsible_owner_id: uuid.UUID | None = None
    notes: str | None = None


class FranchiseeResponse(BaseModel):
    id: uuid.UUID
    company_name: str
    contact_name: str | None
    contact_email: str | None
    contact_phone: str | None
    status: FranchiseeStatus
    responsible_owner_id: uuid.UUID | None
    notes: str | None
    created_at: datetime
    updated_at: datetime
    points_count: int = 0

    model_config = {"from_attributes": True}


class StageUpdate(BaseModel):
    status: FranchiseeStatus


class StageResponse(BaseModel):
    id: uuid.UUID
    status: FranchiseeStatus
    progress: dict

    model_config = {"from_attributes": True}


class TaskCreate(BaseModel):
    title: str
    stage: FranchiseeStatus
    due_date: date | None = None


class TaskStatusUpdate(BaseModel):
    status: TaskStatus


class TaskResponse(BaseModel):
    id: uuid.UUID
    franchisee_id: uuid.UUID
    title: str
    stage: FranchiseeStatus
    status: TaskStatus
    due_date: date | None
    created_at: datetime | None
    completed_at: datetime | None

    model_config = {"from_attributes": True}


class StageProgress(BaseModel):
    stage: str
    total: int
    done: int
    percent: int


class TaskListResponse(BaseModel):
    tasks: list[TaskResponse]
    stage_progress: StageProgress


class NoteCreate(BaseModel):
    text: str
    author: str | None = None


class NoteResponse(BaseModel):
    id: uuid.UUID
    text: str
    author: str | None
    created_at: datetime


class FranchiseePointResponse(BaseModel):
    id: uuid.UUID
    name: str
    address: str
    is_active: bool
    franchisee_id: uuid.UUID | None

    model_config = {"from_attributes": True}


class FranchiseePointAttachRequest(BaseModel):
    point_id: uuid.UUID | None = None
    name: str | None = None
    address: str | None = None

    @model_validator(mode="after")
    def validate_payload(self) -> "FranchiseePointAttachRequest":
        if self.point_id is not None:
            return self
        if self.name and self.address:
            return self
        raise ValueError("Provide either point_id or both name and address")
