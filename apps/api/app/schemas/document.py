import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict


class DocumentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organization_id: uuid.UUID
    project_id: uuid.UUID
    machine_id: uuid.UUID | None
    filename: str
    content_type: str
    size_bytes: int
    document_type: str | None
    revision: str | None
    document_date: date | None
    language: str | None
    sha256: str
    processing_status: str
    supersedes_document_id: uuid.UUID | None
    created_at: datetime
    updated_at: datetime
