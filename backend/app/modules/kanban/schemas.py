"""Pydantic schemas for the Kanban module."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class BoardCreate(BaseModel):
    name: str
    description: str | None = None


class BoardUpdate(BaseModel):
    name: str | None = None
    description: str | None = None


class BoardRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    description: str | None
    owner_id: uuid.UUID
    card_count: int = 0
    created_at: datetime
    updated_at: datetime


class ColumnCreate(BaseModel):
    name: str
    position: int = 0
    color: str | None = "#1890ff"


class ColumnUpdate(BaseModel):
    name: str | None = None
    position: int | None = None
    color: str | None = None


class ColumnRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    board_id: uuid.UUID
    name: str
    position: int
    color: str | None
    created_at: datetime


class ReorderColumnItem(BaseModel):
    id: uuid.UUID
    position: int


ReorderColumns = list[ReorderColumnItem]


class CardCreate(BaseModel):
    title: str
    description: str | None = None
    assignee_id: uuid.UUID | None = None
    deadline: datetime | None = None
    priority: str = "medium"
    tags: list[str] = Field(default_factory=list)
    position: int = 0


class CardUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    assignee_id: uuid.UUID | None = None
    deadline: datetime | None = None
    priority: str | None = None
    tags: list[str] | None = None
    position: int | None = None


class CardMoveRequest(BaseModel):
    column_id: uuid.UUID
    position: int


class CardRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    board_id: uuid.UUID
    column_id: uuid.UUID
    title: str
    description: str | None
    assignee_id: uuid.UUID | None
    deadline: datetime | None
    priority: str
    tags: list[str]
    position: int
    created_by: uuid.UUID
    created_at: datetime
    updated_at: datetime


class CommentCreate(BaseModel):
    body: str


class CommentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    card_id: uuid.UUID
    author_id: uuid.UUID
    body: str
    created_at: datetime


class CustomFieldCreate(BaseModel):
    name: str
    field_type: str
    options: Any | None = None
    position: int = 0


class CustomFieldUpdate(BaseModel):
    name: str | None = None
    field_type: str | None = None
    options: Any | None = None
    position: int | None = None


class CustomFieldRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    board_id: uuid.UUID
    name: str
    field_type: str
    options: Any | None
    position: int


class CardCustomFieldValueRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    card_id: uuid.UUID
    field_id: uuid.UUID
    value: Any | None


CardFieldsUpdate = dict[str, Any]


class CardHistoryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    card_id: uuid.UUID
    from_column_id: uuid.UUID | None
    to_column_id: uuid.UUID
    changed_by: uuid.UUID
    changed_at: datetime


class BoardDetailRead(BoardRead):
    columns: list[ColumnRead] = Field(default_factory=list)
    custom_fields: list[CustomFieldRead] = Field(default_factory=list)
