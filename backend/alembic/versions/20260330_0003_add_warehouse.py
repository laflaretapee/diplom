from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "20260330_0003"
down_revision = "20260330_0002"
branch_labels = None
depends_on = None


movement_type = sa.Enum(
    "in", "out", "adjustment",
    name="movement_type",
    native_enum=False,
)


def upgrade() -> None:
    op.create_table(
        "ingredients",
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("unit", sa.String(length=50), nullable=False),
        sa.Column("min_stock_level", sa.Numeric(10, 3), nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
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
        sa.PrimaryKeyConstraint("id", name=op.f("pk_ingredients")),
        sa.UniqueConstraint("name", name=op.f("uq_ingredients_name")),
    )

    op.create_table(
        "stock_items",
        sa.Column("ingredient_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("point_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("quantity", sa.Numeric(10, 3), nullable=False, server_default="0"),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["ingredient_id"],
            ["ingredients.id"],
            name=op.f("fk_stock_items_ingredient_id_ingredients"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["point_id"],
            ["points.id"],
            name=op.f("fk_stock_items_point_id_points"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_stock_items")),
        sa.UniqueConstraint(
            "ingredient_id", "point_id", name="uq_stock_items_ingredient_point"
        ),
    )

    op.create_table(
        "stock_movements",
        sa.Column("stock_item_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("movement_type", movement_type, nullable=False),
        sa.Column("quantity", sa.Numeric(10, 3), nullable=False),
        sa.Column("reason", sa.String(length=255), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("created_by_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["stock_item_id"],
            ["stock_items.id"],
            name=op.f("fk_stock_movements_stock_item_id_stock_items"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["created_by_id"],
            ["users.id"],
            name=op.f("fk_stock_movements_created_by_id_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_stock_movements")),
    )
    op.create_index(
        op.f("ix_stock_movements_stock_item_id"),
        "stock_movements",
        ["stock_item_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_stock_movements_stock_item_id"), table_name="stock_movements")
    op.drop_table("stock_movements")
    op.drop_table("stock_items")
    op.drop_table("ingredients")
