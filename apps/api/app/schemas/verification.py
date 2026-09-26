import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class VerificationResultCreate(BaseModel):
    observed_value: Any
    unit: str | None = Field(default=None, max_length=50)
    note: str | None = Field(default=None, max_length=4000)
    photo_reference: str | None = Field(default=None, max_length=1000)


class VerificationResultRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organization_id: uuid.UUID
    project_id: uuid.UUID
    verification_task_id: uuid.UUID
    machine_id: uuid.UUID
    fact_key: str
    observed_value: Any
    unit: str | None
    note: str | None
    photo_reference: str | None
    verified_by: str
    verified_at: datetime
    created_at: datetime


class VerificationSubmissionResult(BaseModel):
    verification: VerificationResultRead
    created_fact_candidate_id: uuid.UUID
    state_assertion_id: uuid.UUID | None
