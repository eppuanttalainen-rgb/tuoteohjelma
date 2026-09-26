"""Create state assertions, assertion evidence, and verification tasks.

Revision ID: 0005
Revises: 0004
Create Date: 2026-09-26
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "state_assertions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("machine_id", sa.Uuid(), nullable=False),
        sa.Column("fact_key", sa.String(length=200), nullable=False),
        sa.Column("value", sa.JSON(), nullable=True),
        sa.Column("unit", sa.String(length=50), nullable=True),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("derivation_method", sa.String(length=100), nullable=False),
        sa.Column("derivation_version", sa.String(length=100), nullable=False),
        sa.Column("effective_date", sa.Date(), nullable=True),
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
        sa.ForeignKeyConstraint(["machine_id"], ["machines.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id",
            "machine_id",
            "fact_key",
            name="uq_state_assertions_org_machine_fact",
        ),
    )
    op.create_index(
        "ix_state_assertions_organization_id",
        "state_assertions",
        ["organization_id"],
    )
    op.create_index("ix_state_assertions_project_id", "state_assertions", ["project_id"])
    op.create_index("ix_state_assertions_machine_id", "state_assertions", ["machine_id"])
    op.create_index("ix_state_assertions_fact_key", "state_assertions", ["fact_key"])

    op.create_table(
        "state_assertion_evidence",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("assertion_id", sa.Uuid(), nullable=False),
        sa.Column("fact_candidate_id", sa.Uuid(), nullable=False),
        sa.Column("relationship", sa.String(length=40), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["assertion_id"],
            ["state_assertions.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["fact_candidate_id"],
            ["fact_candidates.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "assertion_id",
            "fact_candidate_id",
            name="uq_assertion_evidence_assertion_candidate",
        ),
    )
    op.create_index(
        "ix_assertion_evidence_organization_id",
        "state_assertion_evidence",
        ["organization_id"],
    )
    op.create_index(
        "ix_assertion_evidence_assertion_id",
        "state_assertion_evidence",
        ["assertion_id"],
    )
    op.create_index(
        "ix_assertion_evidence_fact_candidate_id",
        "state_assertion_evidence",
        ["fact_candidate_id"],
    )

    op.create_table(
        "verification_tasks",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("machine_id", sa.Uuid(), nullable=False),
        sa.Column("fact_key", sa.String(length=200), nullable=False),
        sa.Column("reason_code", sa.String(length=100), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("instructions", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("resolution_value", sa.JSON(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["machine_id"], ["machines.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id",
            "machine_id",
            "fact_key",
            "reason_code",
            name="uq_verification_tasks_org_machine_fact_reason",
        ),
    )
    op.create_index(
        "ix_verification_tasks_organization_id",
        "verification_tasks",
        ["organization_id"],
    )
    op.create_index(
        "ix_verification_tasks_project_id",
        "verification_tasks",
        ["project_id"],
    )
    op.create_index(
        "ix_verification_tasks_machine_id",
        "verification_tasks",
        ["machine_id"],
    )
    op.create_index(
        "ix_verification_tasks_fact_key",
        "verification_tasks",
        ["fact_key"],
    )


def downgrade() -> None:
    op.drop_index("ix_verification_tasks_fact_key", table_name="verification_tasks")
    op.drop_index("ix_verification_tasks_machine_id", table_name="verification_tasks")
    op.drop_index("ix_verification_tasks_project_id", table_name="verification_tasks")
    op.drop_index("ix_verification_tasks_organization_id", table_name="verification_tasks")
    op.drop_table("verification_tasks")

    op.drop_index(
        "ix_assertion_evidence_fact_candidate_id",
        table_name="state_assertion_evidence",
    )
    op.drop_index(
        "ix_assertion_evidence_assertion_id",
        table_name="state_assertion_evidence",
    )
    op.drop_index(
        "ix_assertion_evidence_organization_id",
        table_name="state_assertion_evidence",
    )
    op.drop_table("state_assertion_evidence")

    op.drop_index("ix_state_assertions_fact_key", table_name="state_assertions")
    op.drop_index("ix_state_assertions_machine_id", table_name="state_assertions")
    op.drop_index("ix_state_assertions_project_id", table_name="state_assertions")
    op.drop_index("ix_state_assertions_organization_id", table_name="state_assertions")
    op.drop_table("state_assertions")
