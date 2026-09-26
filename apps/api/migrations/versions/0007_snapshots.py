"""Create immutable machine snapshots.

Revision ID: 0007
Revises: 0006
Create Date: 2026-09-26
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0007"
down_revision: str | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "snapshots",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("machine_id", sa.Uuid(), nullable=False),
        sa.Column("snapshot_type", sa.String(length=80), nullable=False),
        sa.Column("status", sa.String(length=80), nullable=False),
        sa.Column("schema_version", sa.String(length=40), nullable=False),
        sa.Column("state_hash", sa.String(length=64), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("created_by", sa.String(length=200), nullable=False),
        sa.Column(
            "created_at",
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
            "state_hash",
            name="uq_snapshots_org_machine_hash",
        ),
    )
    op.create_index("ix_snapshots_organization_id", "snapshots", ["organization_id"])
    op.create_index("ix_snapshots_project_id", "snapshots", ["project_id"])
    op.create_index("ix_snapshots_machine_id", "snapshots", ["machine_id"])
    op.create_index("ix_snapshots_state_hash", "snapshots", ["state_hash"])


def downgrade() -> None:
    op.drop_index("ix_snapshots_state_hash", table_name="snapshots")
    op.drop_index("ix_snapshots_machine_id", table_name="snapshots")
    op.drop_index("ix_snapshots_project_id", table_name="snapshots")
    op.drop_index("ix_snapshots_organization_id", table_name="snapshots")
    op.drop_table("snapshots")
