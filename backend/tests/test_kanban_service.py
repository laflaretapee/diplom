from __future__ import annotations

import uuid
from types import SimpleNamespace

import pytest
from fastapi import HTTPException, status

from backend.app.db import models as _db_models  # noqa: F401
from backend.app.models.user import UserRole
from backend.app.modules.kanban.models import Board
from backend.app.modules.kanban.service import KanbanBoardService


class DummyResult:
    def __init__(self, value):
        self._value = value

    def scalar_one_or_none(self):
        return self._value


class DummyDb:
    def __init__(self, value):
        self._value = value

    async def execute(self, _statement):
        return DummyResult(self._value)


@pytest.mark.asyncio
async def test_get_board_or_404_forbids_non_owner_non_admin() -> None:
    board_id = uuid.uuid4()
    owner_id = uuid.uuid4()
    outsider_id = uuid.uuid4()

    board = Board(id=board_id, name="Sprint", owner_id=owner_id)
    service = KanbanBoardService(DummyDb(board))
    outsider = SimpleNamespace(id=outsider_id, role=UserRole.STAFF)

    with pytest.raises(HTTPException) as exc_info:
        await service.get_board_or_404(board_id, outsider)

    assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN
