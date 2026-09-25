"""Create parsed document pages.

Revision ID: 0003
Revises: 0002
Create Date: 2026-09-25
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "document_pages",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("page_number", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("text_sha256", sa.String(length=64), nullable=False),
        sa.Column("parser_name", sa.String(length=100), nullable=False),
        sa.Column("parser_version", sa.String(length=100), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["document_id"],
            ["documents.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "document_id",
            "page_number",
            name="uq_document_pages_document_page_number",
        ),
    )
    op.create_index(
        "ix_document_pages_document_id",
        "document_pages",
        ["document_id"],
    )
    op.create_index(
        "ix_document_pages_organization_id",
        "document_pages",
        ["organization_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_document_pages_organization_id", table_name="document_pages")
    op.drop_index("ix_document_pages_document_id", table_name="document_pages")
    op.drop_table("document_pages")
