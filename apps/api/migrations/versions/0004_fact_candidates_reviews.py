"""Create fact candidates and review audit.

Revision ID: 0004
Revises: 0003
Create Date: 2026-09-25
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "fact_candidates",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("machine_id", sa.Uuid(), nullable=True),
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("document_page_id", sa.Uuid(), nullable=False),
        sa.Column("fact_key", sa.String(length=200), nullable=False),
        sa.Column("raw_value", sa.Text(), nullable=False),
        sa.Column("normalized_value", sa.JSON(), nullable=False),
        sa.Column("unit", sa.String(length=50), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("source_excerpt", sa.Text(), nullable=False),
        sa.Column("extraction_method", sa.String(length=100), nullable=False),
        sa.Column("extraction_version", sa.String(length=100), nullable=False),
        sa.Column("candidate_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("effective_date", sa.Date(), nullable=True),
        sa.Column("review_state", sa.String(length=40), nullable=False),
        sa.Column("reviewed_value", sa.JSON(), nullable=True),
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
        sa.ForeignKeyConstraint(
            ["document_id"],
            ["documents.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["document_page_id"],
            ["document_pages.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["machine_id"],
            ["machines.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id",
            "candidate_fingerprint",
            name="uq_fact_candidates_org_fingerprint",
        ),
    )
    op.create_index(
        "ix_fact_candidates_document_id",
        "fact_candidates",
        ["document_id"],
    )
    op.create_index(
        "ix_fact_candidates_document_page_id",
        "fact_candidates",
        ["document_page_id"],
    )
    op.create_index("ix_fact_candidates_fact_key", "fact_candidates", ["fact_key"])
    op.create_index("ix_fact_candidates_machine_id", "fact_candidates", ["machine_id"])
    op.create_index(
        "ix_fact_candidates_organization_id",
        "fact_candidates",
        ["organization_id"],
    )
    op.create_index("ix_fact_candidates_project_id", "fact_candidates", ["project_id"])

    op.create_table(
        "fact_reviews",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("candidate_id", sa.Uuid(), nullable=False),
        sa.Column("action", sa.String(length=40), nullable=False),
        sa.Column("previous_state", sa.String(length=40), nullable=False),
        sa.Column("new_state", sa.String(length=40), nullable=False),
        sa.Column("corrected_value", sa.JSON(), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("actor_reference", sa.String(length=200), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["candidate_id"],
            ["fact_candidates.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_fact_reviews_candidate_id",
        "fact_reviews",
        ["candidate_id"],
    )
    op.create_index(
        "ix_fact_reviews_organization_id",
        "fact_reviews",
        ["organization_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_fact_reviews_organization_id", table_name="fact_reviews")
    op.drop_index("ix_fact_reviews_candidate_id", table_name="fact_reviews")
    op.drop_table("fact_reviews")
    op.drop_index("ix_fact_candidates_project_id", table_name="fact_candidates")
    op.drop_index("ix_fact_candidates_organization_id", table_name="fact_candidates")
    op.drop_index("ix_fact_candidates_machine_id", table_name="fact_candidates")
    op.drop_index("ix_fact_candidates_fact_key", table_name="fact_candidates")
    op.drop_index("ix_fact_candidates_document_page_id", table_name="fact_candidates")
    op.drop_index("ix_fact_candidates_document_id", table_name="fact_candidates")
    op.drop_table("fact_candidates")
