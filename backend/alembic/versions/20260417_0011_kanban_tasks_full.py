"""kanban tasks full: add card fields and notification_log

Revision ID: 20260417_0011
Revises: 20260331_0010
Create Date: 2026-04-17 00:00:00
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "20260417_0011"
down_revision = "20260331_0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Add new columns to cards
    op.add_column(
        "cards",
        sa.Column(
            "creator_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id"),
            nullable=True,
        ),
    )
    op.add_column(
        "cards",
        sa.Column(
            "reviewer_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id"),
            nullable=True,
        ),
    )
    op.add_column(
        "cards",
        sa.Column(
            "status",
            sa.String(length=50),
            nullable=False,
            server_default=sa.text("'new'"),
        ),
    )
    op.add_column(
        "cards",
        sa.Column(
            "overdue",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    op.add_column(
        "cards",
        sa.Column(
            "accepted_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )
    op.add_column(
        "cards",
        sa.Column(
            "completed_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )

    # 2. Create notification_log table
    op.create_table(
        "notification_log",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("card_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("event_type", sa.String(length=100), nullable=False),
        sa.Column(
            "channel",
            sa.String(length=20),
            nullable=False,
            server_default=sa.text("'telegram'"),
        ),
        sa.Column(
            "status",
            sa.String(length=20),
            nullable=False,
            server_default=sa.text("'sent'"),
        ),
        sa.Column("telegram_message_id", sa.BigInteger(), nullable=True),
        sa.Column(
            "sent_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("payload", sa.JSON(), nullable=True),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_notification_log_user_id_users"),
        ),
        sa.ForeignKeyConstraint(
            ["card_id"],
            ["cards.id"],
            name=op.f("fk_notification_log_card_id_cards"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_notification_log")),
    )
    op.create_index(
        "ix_notification_log_card_event",
        "notification_log",
        ["card_id", "event_type"],
        unique=False,
    )
    op.create_index(
        "ix_notification_log_user_id",
        "notification_log",
        ["user_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_notification_log_user_id", table_name="notification_log")
    op.drop_index("ix_notification_log_card_event", table_name="notification_log")
    op.drop_table("notification_log")
    op.drop_column("cards", "completed_at")
    op.drop_column("cards", "accepted_at")
    op.drop_column("cards", "overdue")
    op.drop_column("cards", "status")
    op.drop_column("cards", "reviewer_id")
    op.drop_column("cards", "creator_id")
