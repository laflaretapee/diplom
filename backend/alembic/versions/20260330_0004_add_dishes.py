from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "20260330_0004"
down_revision = "20260330_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "dishes",
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("price", sa.Numeric(10, 2), nullable=False),
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
        sa.PrimaryKeyConstraint("id", name=op.f("pk_dishes")),
        sa.UniqueConstraint("name", name=op.f("uq_dishes_name")),
    )

    op.create_table(
        "dish_ingredients",
        sa.Column("dish_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("ingredient_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("quantity_per_portion", sa.Numeric(10, 3), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["dish_id"],
            ["dishes.id"],
            name=op.f("fk_dish_ingredients_dish_id_dishes"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["ingredient_id"],
            ["ingredients.id"],
            name=op.f("fk_dish_ingredients_ingredient_id_ingredients"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_dish_ingredients")),
        sa.UniqueConstraint(
            "dish_id", "ingredient_id", name="uq_dish_ingredients_dish_ingredient"
        ),
    )


def downgrade() -> None:
    op.drop_table("dish_ingredients")
    op.drop_table("dishes")
