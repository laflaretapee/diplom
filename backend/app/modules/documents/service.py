from __future__ import annotations

import re
import uuid
import zipfile
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path, PurePosixPath

from fastapi import HTTPException, UploadFile, status
from sqlalchemy import Select, false, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.events import DomainEvent
from backend.app.core.storage import get_storage_provider
from backend.app.models.franchisee import Franchisee
from backend.app.models.franchisee_task import FranchiseeTask
from backend.app.models.point import Point
from backend.app.models.user import User, UserRole
from backend.app.models.user_point import UserPoint
from backend.app.modules.documents.models import (
    Document,
    DocumentAccessAction,
    DocumentAccessLog,
)
from backend.app.modules.documents.schemas import (
    DocumentAccessLogRead,
    DocumentAuditFilters,
    DocumentListFilters,
)
from backend.app.modules.franchisee.service import (
    get_accessible_point_ids_for_user,
    get_franchisee_ids_for_user,
)
from backend.app.modules.kanban.models import Board, Card

try:
    import magic
except ImportError:  # pragma: no cover
    magic = None

MAX_FILE_SIZE_BYTES = 50 * 1024 * 1024
ENTITY_TYPE_PATTERN = re.compile(r"^[a-z][a-z0-9_-]{0,49}$")

ALLOWED_FILE_TYPES: dict[str, dict[str, str | set[str]]] = {
    ".pdf": {
        "mime": "application/pdf",
        "content_types": {"application/pdf"},
    },
    ".doc": {
        "mime": "application/msword",
        "content_types": {"application/msword"},
    },
    ".docx": {
        "mime": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "content_types": {
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        },
    },
    ".xls": {
        "mime": "application/vnd.ms-excel",
        "content_types": {"application/vnd.ms-excel"},
    },
    ".xlsx": {
        "mime": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "content_types": {"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"},
    },
    ".png": {
        "mime": "image/png",
        "content_types": {"image/png"},
    },
    ".jpg": {
        "mime": "image/jpeg",
        "content_types": {"image/jpeg"},
    },
    ".jpeg": {
        "mime": "image/jpeg",
        "content_types": {"image/jpeg"},
    },
    ".txt": {
        "mime": "text/plain",
        "content_types": {"text/plain"},
    },
}


@dataclass(frozen=True)
class UploadValidationResult:
    extension: str
    mime_type: str


def _normalize_content_type(content_type: str | None) -> str | None:
    if not content_type:
        return None
    return content_type.split(";", 1)[0].strip().lower() or None


def _looks_like_text(sample: bytes) -> bool:
    if not sample:
        return True
    if b"\x00" in sample:
        return False
    try:
        sample.decode("utf-8")
    except UnicodeDecodeError:
        return False
    return True


def _detect_zip_office_extension(sample: bytes) -> str | None:
    if not sample.startswith(b"PK\x03\x04"):
        return None

    try:
        with zipfile.ZipFile(BytesIO(sample)) as archive:
            names = archive.namelist()
    except zipfile.BadZipFile:
        return None

    if any(name.startswith("word/") for name in names):
        return ".docx"
    if any(name.startswith("xl/") for name in names):
        return ".xlsx"
    return None


def _detect_extension_from_bytes(sample: bytes) -> str | None:
    if sample.startswith(b"%PDF-"):
        return ".pdf"
    if sample.startswith(b"\x89PNG\r\n\x1a\n"):
        return ".png"
    if sample.startswith(b"\xff\xd8\xff"):
        return ".jpg"
    if sample.startswith(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"):
        return ".doc"

    office_extension = _detect_zip_office_extension(sample)
    if office_extension:
        return office_extension

    if _looks_like_text(sample):
        return ".txt"
    return None


def _detect_magic_mime(sample: bytes) -> str | None:
    if magic is None or not sample:
        return None
    try:
        detected = magic.from_buffer(sample, mime=True)
    except Exception:  # pragma: no cover
        return None
    if not detected:
        return None
    return detected.strip().lower()


def _extension_matches_detected(
    extension: str,
    detected_extension: str | None,
) -> bool:
    if detected_extension is None:
        return False
    if extension == detected_extension:
        return True
    if extension == ".jpeg" and detected_extension == ".jpg":
        return True
    if extension == ".xls" and detected_extension == ".doc":
        return True
    return False


def _mime_matches_extension(extension: str, mime_type: str | None) -> bool:
    if mime_type is None:
        return False
    allowed = ALLOWED_FILE_TYPES[extension]["content_types"]
    return mime_type in allowed


def validate_document_upload(
    *,
    filename: str | None,
    content_type: str | None,
    size_bytes: int,
    sample: bytes,
) -> UploadValidationResult:
    extension = Path(filename or "").suffix.lower()
    if extension not in ALLOWED_FILE_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File type is not allowed",
        )

    if size_bytes > MAX_FILE_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail="File exceeds 50MB limit",
        )

    detected_extension = _detect_extension_from_bytes(sample)
    if detected_extension is not None and not _extension_matches_detected(
        extension,
        detected_extension,
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File content does not match extension",
        )

    magic_mime = _detect_magic_mime(sample)
    if magic_mime is not None and not _mime_matches_extension(extension, magic_mime):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Detected MIME type is not allowed for this extension",
        )

    normalized_content_type = _normalize_content_type(content_type)
    if detected_extension is None and magic_mime is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unable to verify file type safely",
        )
    if not _mime_matches_extension(extension, normalized_content_type):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Request content type does not match file extension",
        )

    return UploadValidationResult(
        extension=extension,
        mime_type=str(ALLOWED_FILE_TYPES[extension]["mime"]),
    )


async def _get_point_ids_for_user(db: AsyncSession, user_id: uuid.UUID) -> list[uuid.UUID]:
    result = await db.execute(select(UserPoint.point_id).where(UserPoint.user_id == user_id))
    return [row[0] for row in result.all()]


async def _get_entity_scope(
    db: AsyncSession,
    user: User,
) -> tuple[list[uuid.UUID], list[uuid.UUID]]:
    if user.role == UserRole.SUPER_ADMIN:
        return [], []
    if user.role == UserRole.FRANCHISEE:
        franchisee_ids = await get_franchisee_ids_for_user(db, user.id)
        point_ids = await get_accessible_point_ids_for_user(db, user)
        return franchisee_ids, point_ids

    point_ids = await _get_point_ids_for_user(db, user.id)
    return [], point_ids


async def _ensure_entity_exists(
    db: AsyncSession,
    entity_type: str,
    entity_id: uuid.UUID | None,
) -> None:
    if entity_id is None:
        return

    if entity_type == "point":
        query = select(Point.id).where(Point.id == entity_id)
    elif entity_type == "franchisee":
        query = select(Franchisee.id).where(Franchisee.id == entity_id)
    elif entity_type == "task":
        query = select(FranchiseeTask.id).where(FranchiseeTask.id == entity_id)
    elif entity_type == "card":
        query = select(Card.id).where(Card.id == entity_id)
    else:
        return

    result = await db.execute(query)
    if result.scalar_one_or_none() is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"{entity_type.capitalize()} not found",
        )


async def _task_belongs_to_franchisees(
    db: AsyncSession,
    task_id: uuid.UUID,
    franchisee_ids: list[uuid.UUID],
) -> bool:
    if not franchisee_ids:
        return False
    result = await db.execute(
        select(FranchiseeTask.id).where(
            FranchiseeTask.id == task_id,
            FranchiseeTask.franchisee_id.in_(franchisee_ids),
        )
    )
    return result.scalar_one_or_none() is not None


async def _card_is_visible_for_user(
    db: AsyncSession,
    *,
    card_id: uuid.UUID,
    user: User,
) -> bool:
    if user.role == UserRole.SUPER_ADMIN:
        return True

    result = await db.execute(
        select(Card.id)
        .join(Board, Board.id == Card.board_id)
        .where(Card.id == card_id, Board.owner_id == user.id)
    )
    return result.scalar_one_or_none() is not None


async def ensure_document_action_allowed(
    *,
    db: AsyncSession,
    user: User,
    action: DocumentAccessAction,
    entity_type: str,
    entity_id: uuid.UUID | None,
) -> None:
    if user.role == UserRole.SUPER_ADMIN:
        return

    franchisee_ids, point_ids = await _get_entity_scope(db, user)

    if action in {DocumentAccessAction.UPLOAD, DocumentAccessAction.DELETE}:
        if user.role == UserRole.STAFF:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
    if entity_id is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")

    if user.role == UserRole.FRANCHISEE:
        if entity_type == "franchisee" and entity_id in franchisee_ids:
            return
        if entity_type == "point" and entity_id in point_ids:
            return
        if entity_type == "card" and await _card_is_visible_for_user(
            db,
            card_id=entity_id,
            user=user,
        ):
            return
        if entity_type == "task" and await _task_belongs_to_franchisees(
            db,
            entity_id,
            franchisee_ids,
        ):
            return
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")

    if entity_type == "point" and entity_id in point_ids:
        return
    if entity_type == "card" and await _card_is_visible_for_user(
        db,
        card_id=entity_id,
        user=user,
    ):
        return

    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")


async def _apply_document_scope(
    query: Select,
    *,
    db: AsyncSession,
    user: User,
) -> Select:
    if user.role == UserRole.SUPER_ADMIN:
        return query

    franchisee_ids, point_ids = await _get_entity_scope(db, user)

    if user.role == UserRole.FRANCHISEE:
        scope_conditions = []
        if franchisee_ids:
            scope_conditions.append(
                (Document.entity_type == "franchisee") & Document.entity_id.in_(franchisee_ids)
            )
            task_ids_subquery = select(FranchiseeTask.id).where(
                FranchiseeTask.franchisee_id.in_(franchisee_ids)
            )
            scope_conditions.append(
                (Document.entity_type == "task") & Document.entity_id.in_(task_ids_subquery)
            )
        if point_ids:
            scope_conditions.append(
                (Document.entity_type == "point") & Document.entity_id.in_(point_ids)
            )
        owned_card_ids = select(Card.id).join(Board, Board.id == Card.board_id).where(
            Board.owner_id == user.id
        )
        scope_conditions.append(
            (Document.entity_type == "card") & Document.entity_id.in_(owned_card_ids)
        )
        return query.where(or_(*scope_conditions)) if scope_conditions else query.where(false())

    scope_conditions = []
    if point_ids:
        scope_conditions.append(
            (Document.entity_type == "point") & Document.entity_id.in_(point_ids)
        )
    owned_card_ids = select(Card.id).join(Board, Board.id == Card.board_id).where(
        Board.owner_id == user.id
    )
    scope_conditions.append(
        (Document.entity_type == "card") & Document.entity_id.in_(owned_card_ids)
    )
    return query.where(or_(*scope_conditions)) if scope_conditions else query.where(false())


async def record_document_access(
    *,
    db: AsyncSession,
    document_id: uuid.UUID,
    user_id: uuid.UUID,
    action: DocumentAccessAction,
    ip_address: str | None,
) -> None:
    db.add(
        DocumentAccessLog(
            document_id=document_id,
            user_id=user_id,
            action=action,
            ip_address=ip_address,
        )
    )


async def upload_document(
    *,
    db: AsyncSession,
    user: User,
    file: UploadFile,
    entity_type: str,
    entity_id: uuid.UUID | None,
    category: str,
    ip_address: str | None,
) -> Document:
    normalized_entity_type = entity_type.strip().lower()
    normalized_category = category.strip()

    if not ENTITY_TYPE_PATTERN.fullmatch(normalized_entity_type):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid entity_type",
        )
    if not normalized_category:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Category is required",
        )

    await _ensure_entity_exists(db, normalized_entity_type, entity_id)
    await ensure_document_action_allowed(
        db=db,
        user=user,
        action=DocumentAccessAction.UPLOAD,
        entity_type=normalized_entity_type,
        entity_id=entity_id,
    )

    payload = await file.read(MAX_FILE_SIZE_BYTES + 1)
    validation = validate_document_upload(
        filename=file.filename,
        content_type=file.content_type,
        size_bytes=len(payload),
        sample=payload,
    )
    await file.seek(0)

    storage = get_storage_provider()
    entity_segment = str(entity_id) if entity_id is not None else "general"
    subpath = str(PurePosixPath("documents") / normalized_entity_type / entity_segment)
    stored_path = await storage.save(file, subpath)

    document = Document(
        filename=Path(stored_path).name,
        original_filename=file.filename or Path(stored_path).name,
        file_path=stored_path,
        mime_type=validation.mime_type,
        size_bytes=len(payload),
        category=normalized_category,
        entity_type=normalized_entity_type,
        entity_id=entity_id,
        uploaded_by=user.id,
        is_deleted=False,
    )

    try:
        db.add(document)
        await db.flush()
        await record_document_access(
            db=db,
            document_id=document.id,
            user_id=user.id,
            action=DocumentAccessAction.UPLOAD,
            ip_address=ip_address,
        )
        await DomainEvent(db).publish(
            event_type="document.uploaded",
            aggregate_type="document",
            aggregate_id=str(document.id),
            payload={
                "document_id": str(document.id),
                "entity_type": document.entity_type,
                "entity_id": str(document.entity_id) if document.entity_id else None,
                "uploaded_by": str(user.id),
            },
        )
        await db.commit()
    except Exception:
        await storage.delete(stored_path)
        raise

    await db.refresh(document)
    return document


async def list_documents(
    *,
    db: AsyncSession,
    user: User,
    filters: DocumentListFilters,
) -> list[Document]:
    query = select(Document).where(Document.is_deleted.is_(False))
    query = await _apply_document_scope(query, db=db, user=user)

    if filters.entity_type:
        query = query.where(Document.entity_type == filters.entity_type.strip().lower())
    if filters.entity_id is not None:
        query = query.where(Document.entity_id == filters.entity_id)
    if filters.category:
        query = query.where(Document.category == filters.category.strip())
    if filters.q:
        query = query.where(Document.original_filename.ilike(f"%{filters.q.strip()}%"))

    query = query.order_by(Document.created_at.desc()).offset(filters.skip).limit(filters.limit)
    result = await db.execute(query)
    return list(result.scalars().all())


async def get_document_for_access(
    *,
    db: AsyncSession,
    user: User,
    document_id: uuid.UUID,
    action: DocumentAccessAction,
) -> Document:
    result = await db.execute(select(Document).where(Document.id == document_id))
    document = result.scalar_one_or_none()
    if document is None or document.is_deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    await ensure_document_action_allowed(
        db=db,
        user=user,
        action=action,
        entity_type=document.entity_type,
        entity_id=document.entity_id,
    )
    return document


async def prepare_document_download(
    *,
    db: AsyncSession,
    user: User,
    document_id: uuid.UUID,
    ip_address: str | None,
) -> Document:
    document = await get_document_for_access(
        db=db,
        user=user,
        document_id=document_id,
        action=DocumentAccessAction.DOWNLOAD,
    )

    storage = get_storage_provider()
    if not await storage.exists(document.file_path):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Stored file not found")

    await record_document_access(
        db=db,
        document_id=document.id,
        user_id=user.id,
        action=DocumentAccessAction.DOWNLOAD,
        ip_address=ip_address,
    )
    await DomainEvent(db).publish(
        event_type="document.downloaded",
        aggregate_type="document",
        aggregate_id=str(document.id),
        payload={
            "document_id": str(document.id),
            "downloaded_by": str(user.id),
        },
    )
    await db.commit()
    return document


async def delete_document(
    *,
    db: AsyncSession,
    user: User,
    document_id: uuid.UUID,
    ip_address: str | None,
) -> None:
    document = await get_document_for_access(
        db=db,
        user=user,
        document_id=document_id,
        action=DocumentAccessAction.DELETE,
    )

    document.is_deleted = True
    await record_document_access(
        db=db,
        document_id=document.id,
        user_id=user.id,
        action=DocumentAccessAction.DELETE,
        ip_address=ip_address,
    )
    await DomainEvent(db).publish(
        event_type="document.deleted",
        aggregate_type="document",
        aggregate_id=str(document.id),
        payload={
            "document_id": str(document.id),
            "deleted_by": str(user.id),
        },
    )
    await db.commit()

    storage = get_storage_provider()
    await storage.delete(document.file_path)


async def list_document_audit_log(
    *,
    db: AsyncSession,
    user: User,
    filters: DocumentAuditFilters,
) -> list[DocumentAccessLogRead]:
    query = (
        select(
            DocumentAccessLog.id,
            DocumentAccessLog.document_id,
            Document.original_filename.label("document_name"),
            DocumentAccessLog.user_id,
            User.name.label("user_name"),
            DocumentAccessLog.action,
            DocumentAccessLog.ip_address,
            DocumentAccessLog.created_at,
        )
        .join(Document, Document.id == DocumentAccessLog.document_id)
        .join(User, User.id == DocumentAccessLog.user_id)
    )
    query = await _apply_document_scope(query, db=db, user=user)

    if filters.document_id is not None:
        query = query.where(DocumentAccessLog.document_id == filters.document_id)
    if filters.user_id is not None:
        query = query.where(DocumentAccessLog.user_id == filters.user_id)
    if filters.action is not None:
        query = query.where(DocumentAccessLog.action == filters.action)
    if filters.date_from is not None:
        query = query.where(DocumentAccessLog.created_at >= filters.date_from)
    if filters.date_to is not None:
        query = query.where(DocumentAccessLog.created_at <= filters.date_to)

    query = query.order_by(DocumentAccessLog.created_at.desc()).offset(filters.skip).limit(
        filters.limit
    )
    result = await db.execute(query)
    return [DocumentAccessLogRead.model_validate(row._mapping) for row in result.all()]
