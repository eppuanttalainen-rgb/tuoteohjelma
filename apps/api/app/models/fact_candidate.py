import uuid
from datetime import date, datetime

from sqlalchemy import (
    JSON,
    CheckConstraint,
    Date,
    DateTime,
    Float,
    ForeignKey,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class FactCandidate(Base):
    __tablename__ = "fact_candidates"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "candidate_fingerprint",
            name="uq_fact_candidates_org_fingerprint",
        ),
        CheckConstraint(
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
            name="ck_fact_candidates_exactly_one_source",
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
    machine_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("machines.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    source_kind: Mapped[str] = mapped_column(String(40), default="DOCUMENT_PAGE")
    document_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    document_page_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("document_pages.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    verification_result_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("verification_results.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    fact_key: Mapped[str] = mapped_column(String(200), index=True)
    raw_value: Mapped[str] = mapped_column(Text)
    normalized_value: Mapped[object] = mapped_column(JSON)
    unit: Mapped[str | None] = mapped_column(String(50), nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    source_excerpt: Mapped[str] = mapped_column(Text)
    extraction_method: Mapped[str] = mapped_column(String(100))
    extraction_version: Mapped[str] = mapped_column(String(100))
    candidate_fingerprint: Mapped[str] = mapped_column(String(64))
    effective_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    review_state: Mapped[str] = mapped_column(String(40), default="PROPOSED")
    reviewed_value: Mapped[object | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
