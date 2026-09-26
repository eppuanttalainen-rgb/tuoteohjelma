import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class StateAssertionEvidence(Base):
    __tablename__ = "state_assertion_evidence"
    __table_args__ = (
        UniqueConstraint(
            "assertion_id",
            "fact_candidate_id",
            name="uq_assertion_evidence_assertion_candidate",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), index=True)
    assertion_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("state_assertions.id", ondelete="CASCADE"),
        index=True,
    )
    fact_candidate_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("fact_candidates.id", ondelete="CASCADE"),
        index=True,
    )
    relationship: Mapped[str] = mapped_column(String(40))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
