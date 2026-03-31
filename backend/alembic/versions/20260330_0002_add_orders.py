from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "20260330_0002"
down_revision = "20260330_0001"
branch_labels = None
depends_on = None


order_status = sa.Enum(
    "new", "in_progress", "ready", "delivered", "cancelled",
    name="order_status",
    native_enum=False,
)

payment_type = sa.Enum(
    "cash", "card", "online",
    name="payment_type",
    native_enum=False,
)

payment_status = sa.Enum(
    "pending", "paid", "failed", "refunded",
    name="payment_status",
    native_enum=False,
)

source_channel = sa.Enum(
    "website", "mobile_app", "telegram", "vk", "pos",
    name="source_channel",
    native_enum=False,
)


def upgrade() -> None:
    op.create_table(
        "orders",
        sa.Column("point_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", order_status, nullable=False, server_default="new"),
        sa.Column("payment_type", payment_type, nullable=False),
        sa.Column("payment_status", payment_status, nullable=False, server_default="pending"),
        sa.Column("source_channel", source_channel, nullable=False),
        sa.Column("items", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("total_amount", sa.Numeric(10, 2), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(
            ["point_id"],
            ["points.id"],
            name=op.f("fk_orders_point_id_points"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_orders")),
    )
    op.create_index(op.f("ix_orders_point_id"), "orders", ["point_id"], unique=False)
    op.create_index(op.f("ix_orders_status"), "orders", ["status"], unique=False)
    op.create_index(op.f("ix_orders_created_at"), "orders", ["created_at"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_orders_created_at"), table_name="orders")
    op.drop_index(op.f("ix_orders_status"), table_name="orders")
    op.drop_index(op.f("ix_orders_point_id"), table_name="orders")
    op.drop_table("orders")
