"""add documents tables

Revision ID: 20260331_0011
Revises: 20260331_0010
Create Date: 2026-03-31 18:30:00
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "20260331_0011"
down_revision = "20260331_0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "documents",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("original_filename", sa.String(length=255), nullable=False),
        sa.Column("file_path", sa.String(length=500), nullable=False),
        sa.Column("mime_type", sa.String(length=255), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("category", sa.String(length=100), nullable=False),
        sa.Column("entity_type", sa.String(length=50), nullable=False),
        sa.Column("entity_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("uploaded_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "is_deleted",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(
            ["uploaded_by"],
            ["users.id"],
            name=op.f("fk_documents_uploaded_by_users"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_documents")),
        sa.UniqueConstraint("file_path", name=op.f("uq_documents_file_path")),
    )
    op.create_index(op.f("ix_documents_entity_type"), "documents", ["entity_type"], unique=False)
    op.create_index(op.f("ix_documents_entity_id"), "documents", ["entity_id"], unique=False)
    op.create_index(op.f("ix_documents_category"), "documents", ["category"], unique=False)
    op.create_index(op.f("ix_documents_uploaded_by"), "documents", ["uploaded_by"], unique=False)
    op.create_index(op.f("ix_documents_is_deleted"), "documents", ["is_deleted"], unique=False)
    op.create_index(op.f("ix_documents_created_at"), "documents", ["created_at"], unique=False)

    op.create_table(
        "document_access_log",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("action", sa.String(length=20), nullable=False),
        sa.Column("ip_address", sa.String(length=64), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(
            ["document_id"],
            ["documents.id"],
            name=op.f("fk_document_access_log_document_id_documents"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_document_access_log_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_document_access_log")),
    )
    op.create_index(
        op.f("ix_document_access_log_document_id"),
        "document_access_log",
        ["document_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_document_access_log_user_id"),
        "document_access_log",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_document_access_log_action"),
        "document_access_log",
        ["action"],
        unique=False,
    )
    op.create_index(
        op.f("ix_document_access_log_created_at"),
        "document_access_log",
        ["created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_document_access_log_created_at"), table_name="document_access_log")
    op.drop_index(op.f("ix_document_access_log_action"), table_name="document_access_log")
    op.drop_index(op.f("ix_document_access_log_user_id"), table_name="document_access_log")
    op.drop_index(op.f("ix_document_access_log_document_id"), table_name="document_access_log")
    op.drop_table("document_access_log")

    op.drop_index(op.f("ix_documents_created_at"), table_name="documents")
    op.drop_index(op.f("ix_documents_is_deleted"), table_name="documents")
    op.drop_index(op.f("ix_documents_uploaded_by"), table_name="documents")
    op.drop_index(op.f("ix_documents_category"), table_name="documents")
    op.drop_index(op.f("ix_documents_entity_id"), table_name="documents")
    op.drop_index(op.f("ix_documents_entity_type"), table_name="documents")
    op.drop_table("documents")
