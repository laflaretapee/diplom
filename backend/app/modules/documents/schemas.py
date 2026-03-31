from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from backend.app.modules.documents.models import DocumentAccessAction


class DocumentRead(BaseModel):
    id: uuid.UUID
    filename: str
    original_filename: str
    mime_type: str
    size_bytes: int
    category: str
    entity_type: str
    entity_id: uuid.UUID | None
    uploaded_by: uuid.UUID
    created_at: datetime

    model_config = {"from_attributes": True}


class DocumentAccessLogRead(BaseModel):
    id: uuid.UUID
    document_id: uuid.UUID
    document_name: str
    user_id: uuid.UUID
    user_name: str
    action: DocumentAccessAction
    ip_address: str | None
    created_at: datetime


class DocumentListFilters(BaseModel):
    entity_type: str | None = None
    entity_id: uuid.UUID | None = None
    category: str | None = None
    q: str | None = None
    skip: int = Field(default=0, ge=0)
    limit: int = Field(default=50, ge=1, le=100)


class DocumentAuditFilters(BaseModel):
    document_id: uuid.UUID | None = None
    user_id: uuid.UUID | None = None
    action: DocumentAccessAction | None = None
    date_from: datetime | None = None
    date_to: datetime | None = None
    skip: int = Field(default=0, ge=0)
    limit: int = Field(default=50, ge=1, le=100)
