import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.dependencies import OrganizationId
from app.models import Machine, Project
from app.schemas import MachineCreate, MachineRead

router = APIRouter(tags=["machines"])
DbSession = Annotated[AsyncSession, Depends(get_db)]


@router.post(
    "/api/v1/projects/{project_id}/machines",
    response_model=MachineRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_machine(
    project_id: uuid.UUID,
    payload: MachineCreate,
    organization_id: OrganizationId,
    db: DbSession,
) -> Machine:
    project = await db.scalar(
        select(Project).where(
            Project.id == project_id,
            Project.organization_id == organization_id,
        )
    )
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")

    machine = Machine(
        organization_id=organization_id,
        project_id=project_id,
        **payload.model_dump(),
    )
    db.add(machine)
    await db.commit()
    await db.refresh(machine)
    return machine


@router.get("/api/v1/projects/{project_id}/machines", response_model=list[MachineRead])
async def list_project_machines(
    project_id: uuid.UUID,
    organization_id: OrganizationId,
    db: DbSession,
) -> list[Machine]:
    project = await db.scalar(
        select(Project).where(
            Project.id == project_id,
            Project.organization_id == organization_id,
        )
    )
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")

    result = await db.scalars(
        select(Machine)
        .where(
            Machine.project_id == project_id,
            Machine.organization_id == organization_id,
        )
        .order_by(Machine.created_at.asc())
    )
    return list(result)


@router.get("/api/v1/machines/{machine_id}", response_model=MachineRead)
async def get_machine(
    machine_id: uuid.UUID,
    organization_id: OrganizationId,
    db: DbSession,
) -> Machine:
    machine = await db.scalar(
        select(Machine).where(
            Machine.id == machine_id,
            Machine.organization_id == organization_id,
        )
    )
    if machine is None:
        raise HTTPException(status_code=404, detail="Machine not found")
    return machine
