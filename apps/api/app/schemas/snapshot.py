import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class SnapshotRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organization_id: uuid.UUID
    project_id: uuid.UUID
    machine_id: uuid.UUID
    snapshot_type: str
    status: str
    schema_version: str
    state_hash: str
    payload: Any
    created_by: str
    created_at: datetime


class SnapshotSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    machine_id: uuid.UUID
    snapshot_type: str
    status: str
    schema_version: str
    state_hash: str
    created_by: str
    created_at: datetime
