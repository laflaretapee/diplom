from __future__ import annotations

import uuid
from types import SimpleNamespace

import pytest
from fastapi import HTTPException, status

from backend.app.models.user import UserRole
from backend.app.modules.documents import service
from backend.app.modules.documents.models import DocumentAccessAction


def make_user(role: UserRole) -> SimpleNamespace:
    return SimpleNamespace(id=uuid.uuid4(), role=role)


def allow_scope(monkeypatch: pytest.MonkeyPatch, *, franchisee_ids=None, point_ids=None):
    async def fake_get_entity_scope(_db, _user):
        return franchisee_ids or [], point_ids or []

    monkeypatch.setattr(service, "_get_entity_scope", fake_get_entity_scope)


@pytest.mark.asyncio
async def test_super_admin_can_upload_without_entity_id() -> None:
    user = make_user(UserRole.SUPER_ADMIN)

    await service.ensure_document_action_allowed(
        db=SimpleNamespace(),
        user=user,
        action=DocumentAccessAction.UPLOAD,
        entity_type="general",
        entity_id=None,
    )


@pytest.mark.asyncio
async def test_super_admin_can_delete_any_document() -> None:
    user = make_user(UserRole.SUPER_ADMIN)

    await service.ensure_document_action_allowed(
        db=SimpleNamespace(),
        user=user,
        action=DocumentAccessAction.DELETE,
        entity_type="point",
        entity_id=uuid.uuid4(),
    )


@pytest.mark.asyncio
async def test_franchisee_can_upload_own_franchisee_document(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    franchisee_id = uuid.uuid4()
    user = make_user(UserRole.FRANCHISEE)
    allow_scope(monkeypatch, franchisee_ids=[franchisee_id])

    await service.ensure_document_action_allowed(
        db=SimpleNamespace(),
        user=user,
        action=DocumentAccessAction.UPLOAD,
        entity_type="franchisee",
        entity_id=franchisee_id,
    )


@pytest.mark.asyncio
async def test_franchisee_can_download_own_task_document(monkeypatch: pytest.MonkeyPatch) -> None:
    task_id = uuid.uuid4()
    franchisee_id = uuid.uuid4()
    user = make_user(UserRole.FRANCHISEE)
    allow_scope(monkeypatch, franchisee_ids=[franchisee_id])

    async def fake_task_belongs(_db, _task_id, franchisee_ids):
        return _task_id == task_id and franchisee_id in franchisee_ids

    monkeypatch.setattr(service, "_task_belongs_to_franchisees", fake_task_belongs)

    await service.ensure_document_action_allowed(
        db=SimpleNamespace(),
        user=user,
        action=DocumentAccessAction.DOWNLOAD,
        entity_type="task",
        entity_id=task_id,
    )


@pytest.mark.asyncio
async def test_point_manager_can_download_own_point_document(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    point_id = uuid.uuid4()
    user = make_user(UserRole.POINT_MANAGER)
    allow_scope(monkeypatch, point_ids=[point_id])

    await service.ensure_document_action_allowed(
        db=SimpleNamespace(),
        user=user,
        action=DocumentAccessAction.DOWNLOAD,
        entity_type="point",
        entity_id=point_id,
    )


@pytest.mark.asyncio
async def test_point_manager_can_delete_own_card_document(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    card_id = uuid.uuid4()
    user = make_user(UserRole.POINT_MANAGER)
    allow_scope(monkeypatch, point_ids=[uuid.uuid4()])

    async def fake_card_is_visible(_db, *, card_id: uuid.UUID, user: SimpleNamespace) -> bool:
        return card_id == card_id_to_check and user.role == UserRole.POINT_MANAGER

    card_id_to_check = card_id
    monkeypatch.setattr(service, "_card_is_visible_for_user", fake_card_is_visible)

    await service.ensure_document_action_allowed(
        db=SimpleNamespace(),
        user=user,
        action=DocumentAccessAction.DELETE,
        entity_type="card",
        entity_id=card_id,
    )


@pytest.mark.asyncio
async def test_staff_cannot_upload_documents(monkeypatch: pytest.MonkeyPatch) -> None:
    user = make_user(UserRole.STAFF)
    allow_scope(monkeypatch, point_ids=[uuid.uuid4()])

    with pytest.raises(HTTPException) as exc_info:
        await service.ensure_document_action_allowed(
            db=SimpleNamespace(),
            user=user,
            action=DocumentAccessAction.UPLOAD,
            entity_type="point",
            entity_id=uuid.uuid4(),
        )

    assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.asyncio
async def test_staff_cannot_download_foreign_point_document(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user = make_user(UserRole.STAFF)
    allow_scope(monkeypatch, point_ids=[uuid.uuid4()])

    with pytest.raises(HTTPException) as exc_info:
        await service.ensure_document_action_allowed(
            db=SimpleNamespace(),
            user=user,
            action=DocumentAccessAction.DOWNLOAD,
            entity_type="point",
            entity_id=uuid.uuid4(),
        )

    assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN
