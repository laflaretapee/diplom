"""add user notification settings

Revision ID: 20260331_0006
Revises: 20260330_0005
Create Date: 2026-03-31 10:00:00
"""

from alembic import op
import sqlalchemy as sa


revision = "20260331_0006"
down_revision = "20260330_0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "notification_settings",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'{}'::json"),
        ),
    )
    op.alter_column("users", "notification_settings", server_default=None)


def downgrade() -> None:
    op.drop_column("users", "notification_settings")
