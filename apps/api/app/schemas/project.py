import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ProjectCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    customer_reference: str | None = Field(default=None, max_length=200)
    objective: str | None = None
    jurisdiction: str | None = Field(default=None, max_length=50)


class ProjectRead(ProjectCreate):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organization_id: uuid.UUID
    status: str
    created_at: datetime
    updated_at: datetime
