"""Business logic for the Kanban module."""
from __future__ import annotations

import uuid
from collections.abc import Iterable
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.app.core.events import DomainEvent
from backend.app.models.user import User, UserRole
from backend.app.modules.kanban.models import (
    Board,
    BoardColumn,
    Card,
    CardComment,
    CardCustomFieldValue,
    CardHistory,
    CustomFieldDefinition,
)
from backend.app.modules.kanban.schemas import (
    BoardCreate,
    BoardUpdate,
    CardCreate,
    CardFieldsUpdate,
    CardMoveRequest,
    CardUpdate,
    ColumnCreate,
    ColumnUpdate,
    CommentCreate,
    CustomFieldCreate,
    CustomFieldUpdate,
    ReorderColumns,
)


class KanbanBoardService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    def _ensure_board_access(self, owner_id: uuid.UUID, actor: User) -> None:
        if actor.role == UserRole.SUPER_ADMIN:
            return
        if owner_id != actor.id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")

    async def create_board(self, actor: User, data: BoardCreate) -> Board:
        board = Board(
            name=data.name,
            description=data.description,
            owner_id=actor.id,
        )
        self.db.add(board)
        await self.db.commit()
        await self.db.refresh(board)
        return board

    async def list_boards(self, actor: User) -> list[Board]:
        query = (
            select(Board, func.count(Card.id))
            .outerjoin(Card, Card.board_id == Board.id)
            .group_by(Board.id)
            .order_by(Board.created_at, Board.name)
        )
        if actor.role != UserRole.SUPER_ADMIN:
            query = query.where(Board.owner_id == actor.id)
        result = await self.db.execute(query)
        boards: list[Board] = []
        for board, card_count in result.all():
            board.card_count = int(card_count or 0)
            boards.append(board)
        return boards

    async def get_board_or_404(self, board_id: uuid.UUID, actor: User) -> Board:
        result = await self.db.execute(
            select(Board)
            .options(
                selectinload(Board.columns),
                selectinload(Board.custom_fields),
            )
            .where(Board.id == board_id)
        )
        board = result.scalar_one_or_none()
        if board is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Board not found")
        self._ensure_board_access(board.owner_id, actor)
        return board

    async def update_board(self, board_id: uuid.UUID, actor: User, data: BoardUpdate) -> Board:
        board = await self.get_board_or_404(board_id, actor)
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(board, field, value)
        await self.db.commit()
        await self.db.refresh(board)
        return board

    async def delete_board(self, board_id: uuid.UUID, actor: User) -> None:
        board = await self.get_board_or_404(board_id, actor)
        await self.db.delete(board)
        await self.db.commit()

    async def list_columns(self, board_id: uuid.UUID, actor: User) -> list[BoardColumn]:
        await self.get_board_or_404(board_id, actor)
        result = await self.db.execute(
            select(BoardColumn)
            .where(BoardColumn.board_id == board_id)
            .order_by(BoardColumn.position, BoardColumn.created_at)
        )
        return list(result.scalars().all())

    async def create_column(
        self,
        board_id: uuid.UUID,
        actor: User,
        data: ColumnCreate,
    ) -> BoardColumn:
        await self.get_board_or_404(board_id, actor)
        column = BoardColumn(
            board_id=board_id,
            name=data.name,
            position=data.position,
            color=data.color,
        )
        self.db.add(column)
        await self.db.commit()
        await self.db.refresh(column)
        return column

    async def _get_column_row_or_404(
        self,
        column_id: uuid.UUID,
    ) -> tuple[BoardColumn, uuid.UUID]:
        result = await self.db.execute(
            select(BoardColumn, Board.owner_id)
            .join(Board, Board.id == BoardColumn.board_id)
            .where(BoardColumn.id == column_id)
        )
        row = result.one_or_none()
        if row is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Column not found")
        return row

    async def get_column_or_404(self, column_id: uuid.UUID, actor: User) -> BoardColumn:
        column, owner_id = await self._get_column_row_or_404(column_id)
        self._ensure_board_access(owner_id, actor)
        return column

    async def update_column(
        self,
        column_id: uuid.UUID,
        actor: User,
        data: ColumnUpdate,
    ) -> BoardColumn:
        column = await self.get_column_or_404(column_id, actor)
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(column, field, value)
        await self.db.commit()
        await self.db.refresh(column)
        return column

    async def reorder_columns(
        self,
        board_id: uuid.UUID,
        actor: User,
        items: ReorderColumns,
    ) -> list[BoardColumn]:
        await self.get_board_or_404(board_id, actor)
        ids = [item.id for item in items]
        result = await self.db.execute(
            select(BoardColumn)
            .where(BoardColumn.board_id == board_id, BoardColumn.id.in_(ids))
            .order_by(BoardColumn.position)
        )
        columns = {column.id: column for column in result.scalars().all()}
        if len(columns) != len(ids):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="One or more columns were not found",
            )
        for item in items:
            columns[item.id].position = item.position
        await self.db.commit()
        return [columns[item.id] for item in items]

    async def delete_column(self, column_id: uuid.UUID, actor: User) -> None:
        column = await self.get_column_or_404(column_id, actor)
        cards_count = await self.db.scalar(
            select(func.count(Card.id)).where(Card.column_id == column.id)
        )
        if cards_count:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Cannot delete a column that still contains cards",
            )
        await self.db.delete(column)
        await self.db.commit()

    async def _get_card_row_or_404(self, card_id: uuid.UUID) -> tuple[Card, uuid.UUID]:
        result = await self.db.execute(
            select(Card, Board.owner_id)
            .join(Board, Board.id == Card.board_id)
            .where(Card.id == card_id)
        )
        row = result.one_or_none()
        if row is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Card not found")
        return row

    async def get_card_or_404(self, card_id: uuid.UUID, actor: User) -> Card:
        card, owner_id = await self._get_card_row_or_404(card_id)
        self._ensure_board_access(owner_id, actor)
        return card

    async def create_card(
        self,
        column_id: uuid.UUID,
        actor: User,
        data: CardCreate,
    ) -> Card:
        column = await self.get_column_or_404(column_id, actor)
        card = Card(
            board_id=column.board_id,
            column_id=column.id,
            title=data.title,
            description=data.description,
            assignee_id=data.assignee_id,
            deadline=data.deadline,
            priority=data.priority,
            tags=data.tags,
            position=data.position,
            created_by=actor.id,
            creator_id=actor.id,
        )
        self.db.add(card)
        await self.db.flush()

        await DomainEvent(self.db).publish(
            event_type="card.created",
            aggregate_type="card",
            aggregate_id=str(card.id),
            payload={
                "card_id": str(card.id),
                "board_id": str(card.board_id),
                "column_id": str(card.column_id),
                "triggered_by": str(actor.id),
            },
        )

        if data.assignee_id is not None:
            await DomainEvent(self.db).publish(
                event_type="card.assigned",
                aggregate_type="card",
                aggregate_id=str(card.id),
                payload={
                    "card_id": str(card.id),
                    "board_id": str(card.board_id),
                    "assignee_id": str(data.assignee_id),
                    "triggered_by": str(actor.id),
                },
            )

        await self.db.commit()
        await self.db.refresh(card)

        from backend.app.modules.kanban.notifications import notify_task_created
        from backend.app.modules.kanban.tasks import (
            send_card_assigned_notification,
            send_card_deadline_set_notification,
        )

        if data.assignee_id is not None:
            send_card_assigned_notification.delay(str(card.id), str(data.assignee_id))
        if data.deadline is not None:
            send_card_deadline_set_notification.delay(str(card.id))

        try:
            await notify_task_created(self.db, card)
        except Exception:
            import logging as _logging
            _logging.getLogger(__name__).exception(
                "notify_task_created failed for card %s", card.id
            )

        return card

    async def list_cards_by_board(
        self,
        board_id: uuid.UUID,
        actor: User,
    ) -> dict[str, list[Card]]:
        board = await self.get_board_or_404(board_id, actor)
        grouped: dict[str, list[Card]] = {str(column.id): [] for column in board.columns}
        result = await self.db.execute(
            select(Card)
            .where(Card.board_id == board_id)
            .order_by(Card.column_id, Card.position, Card.created_at)
        )
        for card in result.scalars().all():
            grouped.setdefault(str(card.column_id), []).append(card)
        return grouped

    async def update_card(
        self,
        card_id: uuid.UUID,
        actor: User,
        data: CardUpdate,
    ) -> Card:
        import logging as _logging
        from datetime import UTC
        from datetime import datetime as _datetime

        from backend.app.modules.kanban.notifications import (
            notify_task_assigned,
            notify_task_completed,
            notify_task_returned,
        )

        card = await self.get_card_or_404(card_id, actor)
        current_assignee = card.assignee_id
        current_deadline = card.deadline
        current_status = card.status
        updates = data.model_dump(exclude_unset=True)
        for field, value in updates.items():
            setattr(card, field, value)

        should_notify_assignee = False
        if (
            "assignee_id" in updates
            and card.assignee_id is not None
            and card.assignee_id != current_assignee
        ):
            await DomainEvent(self.db).publish(
                event_type="card.assigned",
                aggregate_type="card",
                aggregate_id=str(card.id),
                payload={
                    "card_id": str(card.id),
                    "board_id": str(card.board_id),
                    "assignee_id": str(card.assignee_id),
                    "triggered_by": str(actor.id),
                },
            )
            should_notify_assignee = True

        should_notify_deadline = (
            "deadline" in updates
            and card.deadline is not None
            and card.deadline != current_deadline
        )

        new_status = card.status
        status_changed = "status" in updates and new_status != current_status

        # Set completed_at when transitioning to in_review (completed by assignee)
        if status_changed and new_status == "in_review" and card.completed_at is None:
            card.completed_at = _datetime.now(UTC)

        await self.db.commit()
        await self.db.refresh(card)

        from backend.app.modules.kanban.tasks import (
            send_card_assigned_notification,
            send_card_deadline_set_notification,
        )

        if should_notify_assignee and card.assignee_id is not None:
            send_card_assigned_notification.delay(str(card.id), str(card.assignee_id))
            try:
                await notify_task_assigned(self.db, card, card.assignee_id, assigner_id=actor.id)
            except Exception:
                _logging.getLogger(__name__).exception(
                    "notify_task_assigned failed for card %s", card.id
                )
        if should_notify_deadline:
            send_card_deadline_set_notification.delay(str(card.id))

        if status_changed:
            try:
                if new_status == "in_review":
                    await notify_task_completed(self.db, card)
                elif new_status == "in_progress" and current_status == "in_review":
                    await notify_task_returned(self.db, card)
            except Exception:
                _logging.getLogger(__name__).exception(
                    "status-change notification failed for card %s (new=%s)", card.id, new_status
                )

        return card

    async def move_card(
        self,
        card_id: uuid.UUID,
        actor: User,
        data: CardMoveRequest,
    ) -> Card:
        card = await self.get_card_or_404(card_id, actor)
        target_column = await self.get_column_or_404(data.column_id, actor)
        if target_column.board_id != card.board_id:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Card can only be moved within the same board",
            )

        history = CardHistory(
            card_id=card.id,
            from_column_id=card.column_id,
            to_column_id=target_column.id,
            changed_by=actor.id,
        )
        self.db.add(history)

        previous_column_id = card.column_id
        card.column_id = target_column.id
        card.position = data.position

        await DomainEvent(self.db).publish(
            event_type="card.moved",
            aggregate_type="card",
            aggregate_id=str(card.id),
            payload={
                "card_id": str(card.id),
                "board_id": str(card.board_id),
                "from_column_id": str(previous_column_id),
                "to_column_id": str(target_column.id),
                "triggered_by": str(actor.id),
            },
        )

        await self.db.commit()
        await self.db.refresh(card)
        return card

    async def delete_card(self, card_id: uuid.UUID, actor: User) -> None:
        card = await self.get_card_or_404(card_id, actor)
        await self.db.delete(card)
        await self.db.commit()

    async def get_card_history(self, card_id: uuid.UUID, actor: User) -> list[CardHistory]:
        await self.get_card_or_404(card_id, actor)
        result = await self.db.execute(
            select(CardHistory)
            .where(CardHistory.card_id == card_id)
            .order_by(CardHistory.changed_at)
        )
        return list(result.scalars().all())

    async def create_comment(
        self,
        card_id: uuid.UUID,
        actor: User,
        data: CommentCreate,
    ) -> CardComment:
        card = await self.get_card_or_404(card_id, actor)
        comment = CardComment(
            card_id=card.id,
            author_id=actor.id,
            body=data.body,
        )
        self.db.add(comment)
        await self.db.flush()

        await DomainEvent(self.db).publish(
            event_type="kanban.card.commented",
            aggregate_type="card",
            aggregate_id=str(card.id),
            payload={
                "card_id": str(card.id),
                "board_id": str(card.board_id),
                "comment_id": str(comment.id),
                "author_id": str(actor.id),
            },
        )

        await self.db.commit()
        await self.db.refresh(comment)

        try:
            from backend.app.modules.kanban.notifications import notify_comment_added

            await notify_comment_added(self.db, card, actor.id, data.body)
        except Exception:
            import logging as _logging

            _logging.getLogger(__name__).exception(
                "notify_comment_added failed for card %s", card.id
            )

        return comment

    async def list_comments(self, card_id: uuid.UUID, actor: User) -> list[CardComment]:
        await self.get_card_or_404(card_id, actor)
        result = await self.db.execute(
            select(CardComment)
            .where(CardComment.card_id == card_id)
            .order_by(CardComment.created_at)
        )
        return list(result.scalars().all())

    async def delete_comment(self, comment_id: uuid.UUID, actor: User) -> None:
        result = await self.db.execute(
            select(CardComment, Board.owner_id)
            .join(Card, Card.id == CardComment.card_id)
            .join(Board, Board.id == Card.board_id)
            .where(CardComment.id == comment_id)
        )
        row = result.one_or_none()
        if row is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Comment not found")

        comment, owner_id = row
        self._ensure_board_access(owner_id, actor)
        if (
            actor.role != UserRole.SUPER_ADMIN
            and comment.author_id != actor.id
            and owner_id != actor.id
        ):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")

        await self.db.delete(comment)
        await self.db.commit()

    async def create_custom_field(
        self,
        board_id: uuid.UUID,
        actor: User,
        data: CustomFieldCreate,
    ) -> CustomFieldDefinition:
        await self.get_board_or_404(board_id, actor)
        field = CustomFieldDefinition(
            board_id=board_id,
            name=data.name,
            field_type=data.field_type,
            options=data.options,
            position=data.position,
        )
        self.db.add(field)
        await self.db.commit()
        await self.db.refresh(field)
        return field

    async def list_custom_fields(
        self,
        board_id: uuid.UUID,
        actor: User,
    ) -> list[CustomFieldDefinition]:
        await self.get_board_or_404(board_id, actor)
        result = await self.db.execute(
            select(CustomFieldDefinition)
            .where(CustomFieldDefinition.board_id == board_id)
            .order_by(CustomFieldDefinition.position, CustomFieldDefinition.name)
        )
        return list(result.scalars().all())

    async def _get_custom_field_row_or_404(
        self,
        field_id: uuid.UUID,
    ) -> tuple[CustomFieldDefinition, uuid.UUID]:
        result = await self.db.execute(
            select(CustomFieldDefinition, Board.owner_id)
            .join(Board, Board.id == CustomFieldDefinition.board_id)
            .where(CustomFieldDefinition.id == field_id)
        )
        row = result.one_or_none()
        if row is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Custom field not found",
            )
        return row

    async def update_custom_field(
        self,
        field_id: uuid.UUID,
        actor: User,
        data: CustomFieldUpdate,
    ) -> CustomFieldDefinition:
        field, owner_id = await self._get_custom_field_row_or_404(field_id)
        self._ensure_board_access(owner_id, actor)
        for key, value in data.model_dump(exclude_unset=True).items():
            setattr(field, key, value)
        await self.db.commit()
        await self.db.refresh(field)
        return field

    async def delete_custom_field(self, field_id: uuid.UUID, actor: User) -> None:
        field, owner_id = await self._get_custom_field_row_or_404(field_id)
        self._ensure_board_access(owner_id, actor)
        await self.db.delete(field)
        await self.db.commit()

    async def update_card_custom_fields(
        self,
        card_id: uuid.UUID,
        actor: User,
        updates: CardFieldsUpdate,
    ) -> list[CardCustomFieldValue]:
        card = await self.get_card_or_404(card_id, actor)
        parsed_updates = self._parse_card_field_updates(updates.items())
        field_ids = list(parsed_updates.keys())

        result = await self.db.execute(
            select(CustomFieldDefinition)
            .where(
                CustomFieldDefinition.board_id == card.board_id,
                CustomFieldDefinition.id.in_(field_ids),
            )
            .order_by(CustomFieldDefinition.position)
        )
        fields = {field.id: field for field in result.scalars().all()}
        if len(fields) != len(field_ids):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="One or more custom fields were not found on this board",
            )

        existing_result = await self.db.execute(
            select(CardCustomFieldValue).where(
                CardCustomFieldValue.card_id == card.id,
                CardCustomFieldValue.field_id.in_(field_ids),
            )
        )
        existing_values = {
            value.field_id: value for value in existing_result.scalars().all()
        }

        updated_values: list[CardCustomFieldValue] = []
        for field_id in field_ids:
            value = parsed_updates[field_id]
            existing = existing_values.get(field_id)
            if existing is None:
                existing = CardCustomFieldValue(
                    card_id=card.id,
                    field_id=field_id,
                    value=value,
                )
                self.db.add(existing)
            else:
                existing.value = value
            updated_values.append(existing)

        await self.db.commit()
        for value in updated_values:
            await self.db.refresh(value)
        return updated_values

    @staticmethod
    def _parse_card_field_updates(
        items: Iterable[tuple[str, Any]],
    ) -> dict[uuid.UUID, Any]:
        parsed: dict[uuid.UUID, Any] = {}
        for field_id_str, value in items:
            try:
                field_id = uuid.UUID(field_id_str)
            except ValueError as exc:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=f"Invalid custom field id: {field_id_str}",
                ) from exc
            parsed[field_id] = value
        return parsed
