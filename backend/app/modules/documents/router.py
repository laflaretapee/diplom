from __future__ import annotations

import uuid
from datetime import datetime
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, Form, Query, Request, UploadFile, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.deps import get_current_user, require_any_role, require_roles
from backend.app.db.session import get_db_session
from backend.app.models.user import User, UserRole
from backend.app.modules.documents import service
from backend.app.modules.documents.models import DocumentAccessAction
from backend.app.modules.documents.schemas import (
    DocumentAccessLogRead,
    DocumentAuditFilters,
    DocumentListFilters,
    DocumentRead,
)

router = APIRouter(prefix="/documents", tags=["documents"])

DOCUMENT_FILE = File(...)
DOCUMENT_ENTITY_TYPE = Form(...)
DOCUMENT_ENTITY_ID = Form(default=None)
DOCUMENT_CATEGORY = Form(...)
DOCUMENTS_USER = Depends(require_any_role)
DOCUMENTS_DB = Depends(get_db_session)
AUDIT_USER = Depends(require_roles(UserRole.SUPER_ADMIN, UserRole.FRANCHISEE))
CURRENT_USER = Depends(get_current_user)


def _client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


@router.post("/upload", response_model=DocumentRead, status_code=status.HTTP_201_CREATED)
async def upload_document(
    request: Request,
    file: UploadFile = DOCUMENT_FILE,
    entity_type: str = DOCUMENT_ENTITY_TYPE,
    entity_id: uuid.UUID | None = DOCUMENT_ENTITY_ID,
    category: str = DOCUMENT_CATEGORY,
    user: User = DOCUMENTS_USER,
    db: AsyncSession = DOCUMENTS_DB,
) -> DocumentRead:
    document = await service.upload_document(
        db=db,
        user=user,
        file=file,
        entity_type=entity_type,
        entity_id=entity_id,
        category=category,
        ip_address=_client_ip(request),
    )
    return DocumentRead.model_validate(document)


@router.get("", response_model=list[DocumentRead])
async def list_documents(
    entity_type: str | None = None,
    entity_id: uuid.UUID | None = None,
    category: str | None = None,
    q: str | None = None,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
    user: User = DOCUMENTS_USER,
    db: AsyncSession = DOCUMENTS_DB,
) -> list[DocumentRead]:
    documents = await service.list_documents(
        db=db,
        user=user,
        filters=DocumentListFilters(
            entity_type=entity_type,
            entity_id=entity_id,
            category=category,
            q=q,
            skip=skip,
            limit=limit,
        ),
    )
    return [DocumentRead.model_validate(document) for document in documents]


@router.get("/audit-log", response_model=list[DocumentAccessLogRead])
async def get_document_audit_log(
    document_id: uuid.UUID | None = None,
    user_id: uuid.UUID | None = None,
    action: DocumentAccessAction | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
    user: User = AUDIT_USER,
    db: AsyncSession = DOCUMENTS_DB,
) -> list[DocumentAccessLogRead]:
    return await service.list_document_audit_log(
        db=db,
        user=user,
        filters=DocumentAuditFilters(
            document_id=document_id,
            user_id=user_id,
            action=action,
            date_from=date_from,
            date_to=date_to,
            skip=skip,
            limit=limit,
        ),
    )


@router.get("/{document_id}/download")
async def download_document(
    document_id: uuid.UUID,
    request: Request,
    user: User = CURRENT_USER,
    db: AsyncSession = DOCUMENTS_DB,
) -> StreamingResponse:
    document = await service.prepare_document_download(
        db=db,
        user=user,
        document_id=document_id,
        ip_address=_client_ip(request),
    )
    stream = service.get_storage_provider().get_stream(document.file_path)
    filename = quote(document.original_filename)
    headers = {
        "Content-Disposition": f"attachment; filename*=UTF-8''{filename}",
    }
    return StreamingResponse(stream, media_type=document.mime_type, headers=headers)


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    document_id: uuid.UUID,
    request: Request,
    user: User = DOCUMENTS_USER,
    db: AsyncSession = DOCUMENTS_DB,
) -> None:
    await service.delete_document(
        db=db,
        user=user,
        document_id=document_id,
        ip_address=_client_ip(request),
    )
