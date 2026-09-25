import uuid
from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class FactCandidateRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organization_id: uuid.UUID
    project_id: uuid.UUID
    machine_id: uuid.UUID | None
    document_id: uuid.UUID
    document_page_id: uuid.UUID
    fact_key: str
    raw_value: str
    normalized_value: Any
    unit: str | None
    confidence: float | None
    source_excerpt: str
    extraction_method: str
    extraction_version: str
    effective_date: date | None
    review_state: str
    reviewed_value: Any | None
    created_at: datetime
    updated_at: datetime


class FactExtractionResult(BaseModel):
    document_id: uuid.UUID
    candidates_created: int
    candidates_existing: int
    extraction_method: str
    extraction_version: str


class FactReviewCreate(BaseModel):
    action: Literal["CONFIRMED", "CORRECTED", "REJECTED"]
    corrected_value: Any | None = None
    note: str | None = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def validate_correction(self) -> "FactReviewCreate":
        if self.action == "CORRECTED" and self.corrected_value is None:
            raise ValueError("corrected_value is required for CORRECTED")
        if self.action != "CORRECTED" and self.corrected_value is not None:
            raise ValueError("corrected_value is only allowed for CORRECTED")
        return self


class FactReviewRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organization_id: uuid.UUID
    candidate_id: uuid.UUID
    action: str
    previous_state: str
    new_state: str
    corrected_value: Any | None
    note: str | None
    actor_reference: str
    created_at: datetime
