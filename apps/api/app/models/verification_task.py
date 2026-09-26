import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, JSON, String, Text, UniqueConstraint, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class VerificationTask(Base):
    __tablename__ = "verification_tasks"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "machine_id",
            "fact_key",
            "reason_code",
            name="uq_verification_tasks_org_machine_fact_reason",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), index=True)
    project_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        index=True,
    )
    machine_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("machines.id", ondelete="CASCADE"),
        index=True,
    )
    fact_key: Mapped[str] = mapped_column(String(200), index=True)
    reason_code: Mapped[str] = mapped_column(String(100))
    reason: Mapped[str] = mapped_column(Text)
    instructions: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(40), default="OPEN")
    resolution_value: Mapped[object | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    resolved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
