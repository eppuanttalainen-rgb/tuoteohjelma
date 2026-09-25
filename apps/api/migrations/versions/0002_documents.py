"""Create evidence documents.

Revision ID: 0002
Revises: 0001
Create Date: 2026-09-25
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "documents",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("machine_id", sa.Uuid(), nullable=True),
        sa.Column("filename", sa.String(length=500), nullable=False),
        sa.Column("content_type", sa.String(length=200), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("document_type", sa.String(length=100), nullable=True),
        sa.Column("revision", sa.String(length=100), nullable=True),
        sa.Column("document_date", sa.Date(), nullable=True),
        sa.Column("language", sa.String(length=20), nullable=True),
        sa.Column("storage_key", sa.String(length=1000), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("processing_status", sa.String(length=40), nullable=False),
        sa.Column("supersedes_document_id", sa.Uuid(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["machine_id"], ["machines.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["supersedes_document_id"],
            ["documents.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id",
            "project_id",
            "sha256",
            name="uq_documents_org_project_sha256",
        ),
        sa.UniqueConstraint("storage_key"),
    )
    op.create_index("ix_documents_machine_id", "documents", ["machine_id"])
    op.create_index("ix_documents_organization_id", "documents", ["organization_id"])
    op.create_index("ix_documents_project_id", "documents", ["project_id"])


def downgrade() -> None:
    op.drop_index("ix_documents_project_id", table_name="documents")
    op.drop_index("ix_documents_organization_id", table_name="documents")
    op.drop_index("ix_documents_machine_id", table_name="documents")
    op.drop_table("documents")
