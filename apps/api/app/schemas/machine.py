import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class MachineCreate(BaseModel):
    manufacturer: str | None = Field(default=None, max_length=200)
    model: str | None = Field(default=None, max_length=200)
    serial_number: str | None = Field(default=None, max_length=200)
    year: int | None = Field(default=None, ge=1800, le=2200)
    internal_asset_id: str | None = Field(default=None, max_length=200)
    machine_type: str | None = Field(default=None, max_length=200)


class MachineRead(MachineCreate):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organization_id: uuid.UUID
    project_id: uuid.UUID
    status: str
    created_at: datetime
    updated_at: datetime
