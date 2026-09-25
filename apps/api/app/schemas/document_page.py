import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class DocumentPageRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organization_id: uuid.UUID
    document_id: uuid.UUID
    page_number: int
    text: str
    text_sha256: str
    parser_name: str
    parser_version: str
    created_at: datetime


class DocumentParseResult(BaseModel):
    document_id: uuid.UUID
    processing_status: str
    page_count: int
    parser_name: str
    parser_version: str
