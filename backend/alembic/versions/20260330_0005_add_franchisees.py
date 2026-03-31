from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "20260330_0005"
down_revision = "20260330_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "franchisees",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("company_name", sa.String(length=255), nullable=False),
        sa.Column("contact_name", sa.String(length=255), nullable=True),
        sa.Column("contact_email", sa.String(length=255), nullable=True),
        sa.Column("contact_phone", sa.String(length=50), nullable=True),
        sa.Column(
            "status",
            sa.String(length=50),
            nullable=False,
            server_default="lead",
        ),
        sa.Column("responsible_owner_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
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
            ["responsible_owner_id"],
            ["users.id"],
            name=op.f("fk_franchisees_responsible_owner_id_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_franchisees")),
    )
    op.create_index(
        op.f("ix_franchisees_contact_email"),
        "franchisees",
        ["contact_email"],
        unique=False,
    )

    op.create_table(
        "franchisee_tasks",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("franchisee_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("stage", sa.String(length=50), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False, server_default="pending"),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["franchisee_id"],
            ["franchisees.id"],
            name=op.f("fk_franchisee_tasks_franchisee_id_franchisees"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_franchisee_tasks")),
    )

    # Add FK constraint on points.franchisee_id -> franchisees.id
    # The column already exists as nullable, just add the FK constraint
    op.create_foreign_key(
        "fk_points_franchisee_id_franchisees",
        "points",
        "franchisees",
        ["franchisee_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_points_franchisee_id_franchisees", "points", type_="foreignkey")
    op.drop_table("franchisee_tasks")
    op.drop_index(op.f("ix_franchisees_contact_email"), table_name="franchisees")
    op.drop_table("franchisees")
