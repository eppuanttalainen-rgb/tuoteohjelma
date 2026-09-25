import uuid
from datetime import date, datetime

from sqlalchemy import (
    BigInteger,
    Date,
    DateTime,
    ForeignKey,
    String,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class Document(Base):
    __tablename__ = "documents"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "project_id",
            "sha256",
            name="uq_documents_org_project_sha256",
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
    filename: Mapped[str] = mapped_column(String(500))
    content_type: Mapped[str] = mapped_column(String(200))
    size_bytes: Mapped[int] = mapped_column(BigInteger)
    document_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    revision: Mapped[str | None] = mapped_column(String(100), nullable=True)
    document_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    language: Mapped[str | None] = mapped_column(String(20), nullable=True)
    storage_key: Mapped[str] = mapped_column(String(1000), unique=True)
    sha256: Mapped[str] = mapped_column(String(64))
    processing_status: Mapped[str] = mapped_column(String(40), default="STORED")
    supersedes_document_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("documents.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
