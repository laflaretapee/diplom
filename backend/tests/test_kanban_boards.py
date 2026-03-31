from __future__ import annotations

import uuid
from types import SimpleNamespace

import pytest
from fastapi import HTTPException, status

from backend.app.models.user import UserRole
from backend.app.modules.kanban.models import Board, BoardColumn
from backend.app.modules.kanban.schemas import ReorderColumnItem
from backend.app.modules.kanban.service import KanbanBoardService


class DummyScalarListResult:
    def __init__(self, values):
        self._values = values

    def scalars(self):
        return self

    def all(self):
        return self._values


class DummyAllResult:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return self._rows


class DummyScalarOneResult:
    def __init__(self, value):
        self._value = value

    def scalar_one_or_none(self):
        return self._value


class DummyDb:
    def __init__(self, execute_results=None, *, scalar_value=None):
        self.execute_results = list(execute_results or [])
        self.scalar_value = scalar_value
        self.committed = False
        self.deleted = []

    async def execute(self, _statement):
        return self.execute_results.pop(0)

    async def scalar(self, _statement):
        return self.scalar_value

    async def commit(self):
        self.committed = True

    async def delete(self, value):
        self.deleted.append(value)


@pytest.mark.asyncio
async def test_get_board_or_404_forbids_non_owner_non_admin() -> None:
    board_id = uuid.uuid4()
    owner_id = uuid.uuid4()
    outsider = SimpleNamespace(id=uuid.uuid4(), role=UserRole.STAFF)
    board = Board(id=board_id, name="Sprint", owner_id=owner_id)
    service = KanbanBoardService(DummyDb([DummyScalarOneResult(board)]))

    with pytest.raises(HTTPException) as exc_info:
        await service.get_board_or_404(board_id, outsider)

    assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.asyncio
async def test_list_boards_attaches_card_count() -> None:
    actor = SimpleNamespace(id=uuid.uuid4(), role=UserRole.SUPER_ADMIN)
    board = Board(id=uuid.uuid4(), name="Sprint 1", owner_id=uuid.uuid4())
    service = KanbanBoardService(DummyDb([DummyAllResult([(board, 3)])]))

    boards = await service.list_boards(actor)

    assert boards[0].card_count == 3


@pytest.mark.asyncio
async def test_reorder_columns_updates_positions(monkeypatch: pytest.MonkeyPatch) -> None:
    actor = SimpleNamespace(id=uuid.uuid4(), role=UserRole.SUPER_ADMIN)
    board_id = uuid.uuid4()
    first = BoardColumn(id=uuid.uuid4(), board_id=board_id, name="Todo", position=0, color="#111")
    second = BoardColumn(
        id=uuid.uuid4(),
        board_id=board_id,
        name="Doing",
        position=1,
        color="#222",
    )
    service = KanbanBoardService(DummyDb([DummyScalarListResult([first, second])]))

    async def fake_get_board_or_404(_board_id, actor):
        return Board(id=board_id, name="Sprint", owner_id=actor.id)

    monkeypatch.setattr(service, "get_board_or_404", fake_get_board_or_404)

    reordered = await service.reorder_columns(
        board_id,
        actor,
        [
            ReorderColumnItem(id=second.id, position=0),
            ReorderColumnItem(id=first.id, position=1),
        ],
    )

    assert [column.id for column in reordered] == [second.id, first.id]
    assert second.position == 0
    assert first.position == 1
    assert service.db.committed is True


@pytest.mark.asyncio
async def test_delete_column_rejects_non_empty_column(monkeypatch: pytest.MonkeyPatch) -> None:
    actor = SimpleNamespace(id=uuid.uuid4(), role=UserRole.SUPER_ADMIN)
    column = BoardColumn(
        id=uuid.uuid4(),
        board_id=uuid.uuid4(),
        name="Blocked",
        position=0,
        color="#333",
    )
    service = KanbanBoardService(DummyDb(scalar_value=2))

    async def fake_get_column_or_404(*_args, **_kwargs):
        return column

    monkeypatch.setattr(service, "get_column_or_404", fake_get_column_or_404)

    with pytest.raises(HTTPException) as exc_info:
        await service.delete_column(column.id, actor)

    assert exc_info.value.status_code == status.HTTP_409_CONFLICT
