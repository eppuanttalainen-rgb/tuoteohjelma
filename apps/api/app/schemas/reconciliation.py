import uuid
from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class AssertionEvidenceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    fact_candidate_id: uuid.UUID
    relationship: str


class StateAssertionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organization_id: uuid.UUID
    project_id: uuid.UUID
    machine_id: uuid.UUID
    fact_key: str
    value: Any | None
    unit: str | None
    status: str
    derivation_method: str
    derivation_version: str
    effective_date: date | None
    created_at: datetime
    updated_at: datetime


class StateAssertionDetail(StateAssertionRead):
    evidence: list[AssertionEvidenceRead]


class VerificationTaskRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organization_id: uuid.UUID
    project_id: uuid.UUID
    machine_id: uuid.UUID
    fact_key: str
    reason_code: str
    reason: str
    instructions: str
    status: str
    resolution_value: Any | None
    created_at: datetime
    resolved_at: datetime | None


class ReconciliationResult(BaseModel):
    project_id: uuid.UUID
    assertions_derived: int
    assertions_disputed: int
    assertions_unchanged: int
    verification_tasks_opened: int
    verification_tasks_resolved: int
    derivation_method: str
    derivation_version: str
