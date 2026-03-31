from __future__ import annotations

import uuid
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from backend.app.models.user import UserRole
from backend.app.modules.documents.schemas import DocumentListFilters
from backend.app.modules.kanban import router as kanban_router
from backend.app.modules.kanban import service as kanban_service
from backend.app.modules.kanban.models import Card
from backend.app.modules.kanban.schemas import CommentCreate, CustomFieldCreate
from backend.app.modules.kanban.service import KanbanBoardService


class DummyDb:
    def __init__(self):
        self.added = []
        self.committed = False
        self.refreshed = []

    def add(self, value):
        self.added.append(value)

    async def flush(self):
        return None

    async def commit(self):
        self.committed = True

    async def refresh(self, value):
        self.refreshed.append(value)


@pytest.mark.asyncio
async def test_create_comment_publishes_event(monkeypatch: pytest.MonkeyPatch) -> None:
    actor = SimpleNamespace(id=uuid.uuid4(), role=UserRole.SUPER_ADMIN)
    card = Card(
        id=uuid.uuid4(),
        board_id=uuid.uuid4(),
        column_id=uuid.uuid4(),
        title="Комментарий",
        assignee_id=None,
        deadline=None,
        priority="medium",
        tags=[],
        position=0,
        created_by=actor.id,
    )
    service = KanbanBoardService(DummyDb())
    published_events: list[str] = []

    async def fake_publish(self, *, event_type: str, **_kwargs):
        published_events.append(event_type)

    async def fake_get_card_or_404(_card_id, _actor):
        return card

    monkeypatch.setattr(kanban_service.DomainEvent, "publish", fake_publish)
    monkeypatch.setattr(service, "get_card_or_404", fake_get_card_or_404)

    comment = await service.create_comment(card.id, actor, CommentCreate(body="Нужен апдейт"))

    assert comment.card_id == card.id
    assert comment.author_id == actor.id
    assert published_events == ["kanban.card.commented"]


@pytest.mark.asyncio
async def test_create_custom_field_accepts_list_options(monkeypatch: pytest.MonkeyPatch) -> None:
    actor = SimpleNamespace(id=uuid.uuid4(), role=UserRole.SUPER_ADMIN)
    board_id = uuid.uuid4()
    service = KanbanBoardService(DummyDb())

    async def fake_get_board_or_404(_board_id, _actor):
        return SimpleNamespace(id=board_id, owner_id=actor.id)

    monkeypatch.setattr(service, "get_board_or_404", fake_get_board_or_404)

    field = await service.create_custom_field(
        board_id,
        actor,
        CustomFieldCreate(
            name="Severity",
            field_type="select",
            options=["Low", "Medium", "High"],
            position=0,
        ),
    )

    assert field.options == ["Low", "Medium", "High"]


@pytest.mark.asyncio
async def test_list_card_attachments_reads_documents_with_card_filters(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    card_id = uuid.uuid4()
    user = SimpleNamespace(id=uuid.uuid4(), role=UserRole.SUPER_ADMIN)
    db = SimpleNamespace()
    captured_filters: list[DocumentListFilters] = []
    attachment = SimpleNamespace(
        id=uuid.uuid4(),
        filename="doc.txt",
        original_filename="doc.txt",
        mime_type="text/plain",
        size_bytes=16,
        category="attachment",
        entity_type="card",
        entity_id=card_id,
        uploaded_by=user.id,
        created_at=datetime(2026, 3, 31, tzinfo=timezone.utc),
    )

    async def fake_get_card_or_404(self, _card_id, actor):
        return SimpleNamespace(id=card_id, board_id=uuid.uuid4(), actor=actor)

    async def fake_list_documents(*, filters: DocumentListFilters, **_kwargs):
        captured_filters.append(filters)
        return [attachment]

    monkeypatch.setattr(kanban_service.KanbanBoardService, "get_card_or_404", fake_get_card_or_404)
    monkeypatch.setattr(kanban_router.documents_service, "list_documents", fake_list_documents)

    documents = await kanban_router.list_card_attachments(card_id, user, db)

    assert captured_filters[0].entity_type == "card"
    assert captured_filters[0].entity_id == card_id
    assert documents[0].original_filename == "doc.txt"
