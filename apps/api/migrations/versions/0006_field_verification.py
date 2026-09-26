"""Add field verification provenance.

Revision ID: 0006
Revises: 0005
Create Date: 2026-09-26
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "verification_results",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("verification_task_id", sa.Uuid(), nullable=False),
        sa.Column("machine_id", sa.Uuid(), nullable=False),
        sa.Column("fact_key", sa.String(length=200), nullable=False),
        sa.Column("observed_value", sa.JSON(), nullable=False),
        sa.Column("unit", sa.String(length=50), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("photo_reference", sa.String(length=1000), nullable=True),
        sa.Column("verified_by", sa.String(length=200), nullable=False),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["machine_id"], ["machines.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["verification_task_id"],
            ["verification_tasks.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "verification_task_id",
            name="uq_verification_results_task",
        ),
    )
    op.create_index(
        "ix_verification_results_organization_id",
        "verification_results",
        ["organization_id"],
    )
    op.create_index(
        "ix_verification_results_project_id",
        "verification_results",
        ["project_id"],
    )
    op.create_index(
        "ix_verification_results_verification_task_id",
        "verification_results",
        ["verification_task_id"],
    )
    op.create_index(
        "ix_verification_results_machine_id",
        "verification_results",
        ["machine_id"],
    )
    op.create_index(
        "ix_verification_results_fact_key",
        "verification_results",
        ["fact_key"],
    )

    op.add_column(
        "fact_candidates",
        sa.Column(
            "source_kind",
            sa.String(length=40),
            server_default="DOCUMENT_PAGE",
            nullable=False,
        ),
    )
    op.add_column(
        "fact_candidates",
        sa.Column("verification_result_id", sa.Uuid(), nullable=True),
    )
    op.alter_column("fact_candidates", "document_id", nullable=True)
    op.alter_column("fact_candidates", "document_page_id", nullable=True)
    op.create_foreign_key(
        "fk_fact_candidates_verification_result",
        "fact_candidates",
        "verification_results",
        ["verification_result_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index(
        "ix_fact_candidates_verification_result_id",
        "fact_candidates",
        ["verification_result_id"],
    )
    op.create_check_constraint(
        "ck_fact_candidates_exactly_one_source",
        "fact_candidates",
        "("
        "source_kind = 'DOCUMENT_PAGE' "
        "AND document_id IS NOT NULL "
        "AND document_page_id IS NOT NULL "
        "AND verification_result_id IS NULL"
        ") OR ("
        "source_kind = 'FIELD_VERIFICATION' "
        "AND document_id IS NULL "
        "AND document_page_id IS NULL "
        "AND verification_result_id IS NOT NULL"
        ")",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_fact_candidates_exactly_one_source",
        "fact_candidates",
        type_="check",
    )
    op.drop_index(
        "ix_fact_candidates_verification_result_id",
        table_name="fact_candidates",
    )
    op.drop_constraint(
        "fk_fact_candidates_verification_result",
        "fact_candidates",
        type_="foreignkey",
    )
    op.drop_column("fact_candidates", "verification_result_id")
    op.drop_column("fact_candidates", "source_kind")
    op.alter_column("fact_candidates", "document_page_id", nullable=False)
    op.alter_column("fact_candidates", "document_id", nullable=False)

    op.drop_index("ix_verification_results_fact_key", table_name="verification_results")
    op.drop_index("ix_verification_results_machine_id", table_name="verification_results")
    op.drop_index(
        "ix_verification_results_verification_task_id",
        table_name="verification_results",
    )
    op.drop_index("ix_verification_results_project_id", table_name="verification_results")
    op.drop_index(
        "ix_verification_results_organization_id",
        table_name="verification_results",
    )
    op.drop_table("verification_results")
