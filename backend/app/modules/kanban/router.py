"""FastAPI router for the Kanban module."""
from __future__ import annotations

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, File, Request, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.deps import require_any_role
from backend.app.db.session import get_db_session
from backend.app.models.user import User
from backend.app.modules.documents import service as documents_service
from backend.app.modules.documents.schemas import DocumentListFilters, DocumentRead
from backend.app.modules.kanban import schemas as s
from backend.app.modules.kanban.service import KanbanBoardService

router = APIRouter(prefix="/kanban", tags=["kanban"])
CurrentUser = Annotated[User, Depends(require_any_role)]
DbSession = Annotated[AsyncSession, Depends(get_db_session)]
AttachmentFile = Annotated[UploadFile, File(...)]


def _svc(db: AsyncSession) -> KanbanBoardService:
    return KanbanBoardService(db)


def _serialize_card_field_value(value: Any) -> s.CardCustomFieldValueRead:
    return s.CardCustomFieldValueRead.model_validate(value)


@router.post("/boards", response_model=s.BoardRead, status_code=status.HTTP_201_CREATED)
async def create_board(
    data: s.BoardCreate,
    user: CurrentUser,
    db: DbSession,
) -> s.BoardRead:
    board = await _svc(db).create_board(actor=user, data=data)
    return s.BoardRead.model_validate(board)


@router.get("/boards", response_model=list[s.BoardRead])
async def list_boards(
    user: CurrentUser,
    db: DbSession,
) -> list[s.BoardRead]:
    boards = await _svc(db).list_boards(actor=user)
    return [s.BoardRead.model_validate(board) for board in boards]


@router.get("/boards/{board_id}", response_model=s.BoardDetailRead)
async def get_board(
    board_id: uuid.UUID,
    user: CurrentUser,
    db: DbSession,
) -> s.BoardDetailRead:
    board = await _svc(db).get_board_or_404(board_id, actor=user)
    return s.BoardDetailRead.model_validate(board)


@router.put("/boards/{board_id}", response_model=s.BoardRead)
async def update_board(
    board_id: uuid.UUID,
    data: s.BoardUpdate,
    user: CurrentUser,
    db: DbSession,
) -> s.BoardRead:
    board = await _svc(db).update_board(board_id, actor=user, data=data)
    return s.BoardRead.model_validate(board)


@router.delete("/boards/{board_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_board(
    board_id: uuid.UUID,
    user: CurrentUser,
    db: DbSession,
) -> None:
    await _svc(db).delete_board(board_id, actor=user)


@router.post(
    "/boards/{board_id}/columns",
    response_model=s.ColumnRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_column(
    board_id: uuid.UUID,
    data: s.ColumnCreate,
    user: CurrentUser,
    db: DbSession,
) -> s.ColumnRead:
    column = await _svc(db).create_column(board_id, actor=user, data=data)
    return s.ColumnRead.model_validate(column)


@router.get("/boards/{board_id}/columns", response_model=list[s.ColumnRead])
async def list_columns(
    board_id: uuid.UUID,
    user: CurrentUser,
    db: DbSession,
) -> list[s.ColumnRead]:
    columns = await _svc(db).list_columns(board_id, actor=user)
    return [s.ColumnRead.model_validate(column) for column in columns]


@router.put("/columns/{column_id}", response_model=s.ColumnRead)
async def update_column(
    column_id: uuid.UUID,
    data: s.ColumnUpdate,
    user: CurrentUser,
    db: DbSession,
) -> s.ColumnRead:
    column = await _svc(db).update_column(column_id, actor=user, data=data)
    return s.ColumnRead.model_validate(column)


@router.put("/boards/{board_id}/columns/reorder", response_model=list[s.ColumnRead])
async def reorder_columns(
    board_id: uuid.UUID,
    items: s.ReorderColumns,
    user: CurrentUser,
    db: DbSession,
) -> list[s.ColumnRead]:
    columns = await _svc(db).reorder_columns(board_id, actor=user, items=items)
    return [s.ColumnRead.model_validate(column) for column in columns]


@router.delete("/columns/{column_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_column(
    column_id: uuid.UUID,
    user: CurrentUser,
    db: DbSession,
) -> None:
    await _svc(db).delete_column(column_id, actor=user)


@router.post(
    "/columns/{column_id}/cards",
    response_model=s.CardRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_card(
    column_id: uuid.UUID,
    data: s.CardCreate,
    user: CurrentUser,
    db: DbSession,
) -> s.CardRead:
    card = await _svc(db).create_card(column_id=column_id, actor=user, data=data)
    return s.CardRead.model_validate(card)


@router.get("/boards/{board_id}/cards", response_model=dict[str, list[s.CardRead]])
async def list_cards(
    board_id: uuid.UUID,
    user: CurrentUser,
    db: DbSession,
) -> dict[str, list[s.CardRead]]:
    grouped = await _svc(db).list_cards_by_board(board_id, actor=user)
    return {
        column_id: [s.CardRead.model_validate(card) for card in cards]
        for column_id, cards in grouped.items()
    }


@router.get("/cards/{card_id}", response_model=s.CardRead)
async def get_card(
    card_id: uuid.UUID,
    user: CurrentUser,
    db: DbSession,
) -> s.CardRead:
    card = await _svc(db).get_card_or_404(card_id, actor=user)
    return s.CardRead.model_validate(card)


@router.put("/cards/{card_id}", response_model=s.CardRead)
async def update_card(
    card_id: uuid.UUID,
    data: s.CardUpdate,
    user: CurrentUser,
    db: DbSession,
) -> s.CardRead:
    card = await _svc(db).update_card(card_id, actor=user, data=data)
    return s.CardRead.model_validate(card)


@router.put("/cards/{card_id}/move", response_model=s.CardRead)
async def move_card(
    card_id: uuid.UUID,
    data: s.CardMoveRequest,
    user: CurrentUser,
    db: DbSession,
) -> s.CardRead:
    card = await _svc(db).move_card(card_id, actor=user, data=data)
    return s.CardRead.model_validate(card)


@router.delete("/cards/{card_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_card(
    card_id: uuid.UUID,
    user: CurrentUser,
    db: DbSession,
) -> None:
    await _svc(db).delete_card(card_id, actor=user)


@router.get("/cards/{card_id}/history", response_model=list[s.CardHistoryRead])
async def get_card_history(
    card_id: uuid.UUID,
    user: CurrentUser,
    db: DbSession,
) -> list[s.CardHistoryRead]:
    history = await _svc(db).get_card_history(card_id, actor=user)
    return [s.CardHistoryRead.model_validate(item) for item in history]


@router.post(
    "/cards/{card_id}/comments",
    response_model=s.CommentRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_comment(
    card_id: uuid.UUID,
    data: s.CommentCreate,
    user: CurrentUser,
    db: DbSession,
) -> s.CommentRead:
    comment = await _svc(db).create_comment(card_id, actor=user, data=data)
    return s.CommentRead.model_validate(comment)


@router.get("/cards/{card_id}/comments", response_model=list[s.CommentRead])
async def list_comments(
    card_id: uuid.UUID,
    user: CurrentUser,
    db: DbSession,
) -> list[s.CommentRead]:
    comments = await _svc(db).list_comments(card_id, actor=user)
    return [s.CommentRead.model_validate(comment) for comment in comments]


@router.delete("/comments/{comment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_comment(
    comment_id: uuid.UUID,
    user: CurrentUser,
    db: DbSession,
) -> None:
    await _svc(db).delete_comment(comment_id, actor=user)


@router.post(
    "/boards/{board_id}/custom-fields",
    response_model=s.CustomFieldRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_custom_field(
    board_id: uuid.UUID,
    data: s.CustomFieldCreate,
    user: CurrentUser,
    db: DbSession,
) -> s.CustomFieldRead:
    field = await _svc(db).create_custom_field(board_id, actor=user, data=data)
    return s.CustomFieldRead.model_validate(field)


@router.get("/boards/{board_id}/custom-fields", response_model=list[s.CustomFieldRead])
async def list_custom_fields(
    board_id: uuid.UUID,
    user: CurrentUser,
    db: DbSession,
) -> list[s.CustomFieldRead]:
    fields = await _svc(db).list_custom_fields(board_id, actor=user)
    return [s.CustomFieldRead.model_validate(field) for field in fields]


@router.put("/custom-fields/{field_id}", response_model=s.CustomFieldRead)
async def update_custom_field(
    field_id: uuid.UUID,
    data: s.CustomFieldUpdate,
    user: CurrentUser,
    db: DbSession,
) -> s.CustomFieldRead:
    field = await _svc(db).update_custom_field(field_id, actor=user, data=data)
    return s.CustomFieldRead.model_validate(field)


@router.delete("/custom-fields/{field_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_custom_field(
    field_id: uuid.UUID,
    user: CurrentUser,
    db: DbSession,
) -> None:
    await _svc(db).delete_custom_field(field_id, actor=user)


@router.put("/cards/{card_id}/custom-fields", response_model=list[s.CardCustomFieldValueRead])
async def update_card_custom_fields(
    card_id: uuid.UUID,
    updates: s.CardFieldsUpdate,
    user: CurrentUser,
    db: DbSession,
) -> list[s.CardCustomFieldValueRead]:
    values = await _svc(db).update_card_custom_fields(card_id, actor=user, updates=updates)
    return [_serialize_card_field_value(value) for value in values]


@router.post(
    "/cards/{card_id}/attachments",
    response_model=DocumentRead,
    status_code=status.HTTP_201_CREATED,
)
async def upload_card_attachment(
    card_id: uuid.UUID,
    request: Request,
    file: AttachmentFile,
    user: CurrentUser,
    db: DbSession,
) -> DocumentRead:
    await _svc(db).get_card_or_404(card_id, actor=user)
    document = await documents_service.upload_document(
        db=db,
        user=user,
        file=file,
        entity_type="card",
        entity_id=card_id,
        category="attachment",
        ip_address=request.client.host if request.client else None,
    )
    return DocumentRead.model_validate(document)


@router.get("/cards/{card_id}/attachments", response_model=list[DocumentRead])
async def list_card_attachments(
    card_id: uuid.UUID,
    user: CurrentUser,
    db: DbSession,
) -> list[DocumentRead]:
    await _svc(db).get_card_or_404(card_id, actor=user)
    documents = await documents_service.list_documents(
        db=db,
        user=user,
        filters=DocumentListFilters(
            entity_type="card",
            entity_id=card_id,
            limit=100,
        ),
    )
    return [DocumentRead.model_validate(document) for document in documents]


@router.delete("/cards/{card_id}/attachments/{doc_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_card_attachment(
    card_id: uuid.UUID,
    doc_id: uuid.UUID,
    request: Request,
    user: CurrentUser,
    db: DbSession,
) -> None:
    await _svc(db).get_card_or_404(card_id, actor=user)
    await documents_service.delete_document(
        db=db,
        user=user,
        document_id=doc_id,
        ip_address=request.client.host if request.client else None,
    )
