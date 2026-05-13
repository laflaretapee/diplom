"""customers and telegram sales channel metadata

Revision ID: 20260513_0012
Revises: 20260417_0011
Create Date: 2026-05-13 00:00:00
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "20260513_0012"
down_revision = "20260417_0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "customers",
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("phone", sa.String(length=64), nullable=True),
        sa.Column("delivery_address", sa.String(length=500), nullable=True),
        sa.Column("telegram_id", sa.String(length=64), nullable=True),
        sa.Column("vk_id", sa.String(length=64), nullable=True),
        sa.Column(
            "source",
            sa.Enum("crm", "telegram", "vk", "website", name="customer_source", native_enum=False),
            nullable=False,
            server_default="crm",
        ),
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
        sa.PrimaryKeyConstraint("id", name=op.f("pk_customers")),
    )
    op.create_index(op.f("ix_customers_telegram_id"), "customers", ["telegram_id"], unique=False)
    op.create_index(op.f("ix_customers_vk_id"), "customers", ["vk_id"], unique=False)

    op.add_column(
        "orders",
        sa.Column("customer_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column("orders", sa.Column("delivery_address", sa.String(length=500), nullable=True))
    op.add_column("orders", sa.Column("payment_provider", sa.String(length=64), nullable=True))
    op.add_column("orders", sa.Column("payment_invoice_id", sa.String(length=64), nullable=True))
    op.create_foreign_key(
        op.f("fk_orders_customer_id_customers"),
        "orders",
        "customers",
        ["customer_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(op.f("ix_orders_customer_id"), "orders", ["customer_id"], unique=False)
    op.create_index(
        op.f("ix_orders_payment_invoice_id"),
        "orders",
        ["payment_invoice_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_orders_payment_invoice_id"), table_name="orders")
    op.drop_index(op.f("ix_orders_customer_id"), table_name="orders")
    op.drop_constraint(op.f("fk_orders_customer_id_customers"), "orders", type_="foreignkey")
    op.drop_column("orders", "payment_invoice_id")
    op.drop_column("orders", "payment_provider")
    op.drop_column("orders", "delivery_address")
    op.drop_column("orders", "customer_id")
    op.drop_index(op.f("ix_customers_vk_id"), table_name="customers")
    op.drop_index(op.f("ix_customers_telegram_id"), table_name="customers")
    op.drop_table("customers")
