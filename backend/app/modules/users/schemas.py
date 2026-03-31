"""Pydantic schemas for user management endpoints."""
from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr

from backend.app.models.user import UserRole


class UserCreateRequest(BaseModel):
    email: EmailStr
    password: str
    name: str
    role: UserRole


class UserUpdateRequest(BaseModel):
    role: UserRole | None = None
    is_active: bool | None = None


class UserResponse(BaseModel):
    id: str
    email: str
    name: str
    role: str
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class AssignPointRequest(BaseModel):
    point_id: uuid.UUID
