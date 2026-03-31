from __future__ import annotations

import uuid
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from backend.app.models.user import UserRole
from backend.app.modules.kanban import service as kanban_service
from backend.app.modules.kanban import tasks as kanban_tasks
from backend.app.modules.kanban.models import BoardColumn, Card
from backend.app.modules.kanban.schemas import CardCreate, CardMoveRequest, CardUpdate
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
async def test_create_card_publishes_events_and_schedules_notifications(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    actor = SimpleNamespace(id=uuid.uuid4(), role=UserRole.SUPER_ADMIN)
    assignee_id = uuid.uuid4()
    deadline = datetime(2026, 4, 3, 10, 0, tzinfo=timezone.utc)
    column = BoardColumn(id=uuid.uuid4(), board_id=uuid.uuid4(), name="Todo", position=0)
    service = KanbanBoardService(DummyDb())
    published_events: list[str] = []
    assigned_calls: list[tuple[str, str]] = []
    deadline_calls: list[str] = []

    async def fake_publish(self, *, event_type: str, **_kwargs):
        published_events.append(event_type)

    async def fake_get_column_or_404(_column_id, _actor):
        return column

    monkeypatch.setattr(kanban_service.DomainEvent, "publish", fake_publish)
    monkeypatch.setattr(service, "get_column_or_404", fake_get_column_or_404)
    monkeypatch.setattr(
        kanban_tasks.send_card_assigned_notification,
        "delay",
        lambda card_id, user_id: assigned_calls.append((card_id, user_id)),
    )
    monkeypatch.setattr(
        kanban_tasks.send_card_deadline_set_notification,
        "delay",
        lambda card_id: deadline_calls.append(card_id),
    )

    card = await service.create_card(
        column.id,
        actor,
        CardCreate(
            title="Подготовить макет",
            assignee_id=assignee_id,
            deadline=deadline,
            priority="high",
            tags=["design"],
        ),
    )

    assert card.board_id == column.board_id
    assert published_events == ["card.created", "card.assigned"]
    assert assigned_calls == [(str(card.id), str(assignee_id))]
    assert deadline_calls == [str(card.id)]
    assert service.db.committed is True


@pytest.mark.asyncio
async def test_update_card_schedules_assignment_and_deadline_notifications(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    actor = SimpleNamespace(id=uuid.uuid4(), role=UserRole.SUPER_ADMIN)
    old_assignee = uuid.uuid4()
    new_assignee = uuid.uuid4()
    old_deadline = datetime(2026, 4, 1, 9, 0, tzinfo=timezone.utc)
    new_deadline = datetime(2026, 4, 5, 18, 0, tzinfo=timezone.utc)
    card = Card(
        id=uuid.uuid4(),
        board_id=uuid.uuid4(),
        column_id=uuid.uuid4(),
        title="Договор",
        assignee_id=old_assignee,
        deadline=old_deadline,
        priority="medium",
        tags=[],
        position=0,
        created_by=actor.id,
    )
    service = KanbanBoardService(DummyDb())
    published_events: list[str] = []
    assigned_calls: list[tuple[str, str]] = []
    deadline_calls: list[str] = []

    async def fake_publish(self, *, event_type: str, **_kwargs):
        published_events.append(event_type)

    async def fake_get_card_or_404(_card_id, _actor):
        return card

    monkeypatch.setattr(kanban_service.DomainEvent, "publish", fake_publish)
    monkeypatch.setattr(service, "get_card_or_404", fake_get_card_or_404)
    monkeypatch.setattr(
        kanban_tasks.send_card_assigned_notification,
        "delay",
        lambda card_id, user_id: assigned_calls.append((card_id, user_id)),
    )
    monkeypatch.setattr(
        kanban_tasks.send_card_deadline_set_notification,
        "delay",
        lambda card_id: deadline_calls.append(card_id),
    )

    updated = await service.update_card(
        card.id,
        actor,
        CardUpdate(assignee_id=new_assignee, deadline=new_deadline, priority="high"),
    )

    assert updated.assignee_id == new_assignee
    assert updated.deadline == new_deadline
    assert published_events == ["card.assigned"]
    assert assigned_calls == [(str(card.id), str(new_assignee))]
    assert deadline_calls == [str(card.id)]


@pytest.mark.asyncio
async def test_move_card_records_history_and_event(monkeypatch: pytest.MonkeyPatch) -> None:
    actor = SimpleNamespace(id=uuid.uuid4(), role=UserRole.SUPER_ADMIN)
    source_column_id = uuid.uuid4()
    target_column_id = uuid.uuid4()
    card = Card(
        id=uuid.uuid4(),
        board_id=uuid.uuid4(),
        column_id=source_column_id,
        title="Сделать релиз",
        assignee_id=None,
        deadline=None,
        priority="medium",
        tags=[],
        position=0,
        created_by=actor.id,
    )
    target_column = BoardColumn(
        id=target_column_id,
        board_id=card.board_id,
        name="Done",
        position=1,
    )
    service = KanbanBoardService(DummyDb())
    published_events: list[str] = []

    async def fake_publish(self, *, event_type: str, **_kwargs):
        published_events.append(event_type)

    async def fake_get_card_or_404(_card_id, _actor):
        return card

    async def fake_get_column_or_404(_column_id, _actor):
        return target_column

    monkeypatch.setattr(kanban_service.DomainEvent, "publish", fake_publish)
    monkeypatch.setattr(service, "get_card_or_404", fake_get_card_or_404)
    monkeypatch.setattr(service, "get_column_or_404", fake_get_column_or_404)

    updated = await service.move_card(
        card.id,
        actor,
        CardMoveRequest(column_id=target_column_id, position=2),
    )

    assert updated.column_id == target_column_id
    assert updated.position == 2
    assert published_events == ["card.moved"]
    assert service.db.added

