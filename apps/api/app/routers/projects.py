import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.dependencies import OrganizationId
from app.models import Project
from app.schemas import ProjectCreate, ProjectRead

router = APIRouter(prefix="/api/v1/projects", tags=["projects"])
DbSession = Annotated[AsyncSession, Depends(get_db)]


@router.post("", response_model=ProjectRead, status_code=status.HTTP_201_CREATED)
async def create_project(
    payload: ProjectCreate,
    organization_id: OrganizationId,
    db: DbSession,
) -> Project:
    project = Project(organization_id=organization_id, **payload.model_dump())
    db.add(project)
    await db.commit()
    await db.refresh(project)
    return project


@router.get("", response_model=list[ProjectRead])
async def list_projects(
    organization_id: OrganizationId,
    db: DbSession,
) -> list[Project]:
    result = await db.scalars(
        select(Project)
        .where(Project.organization_id == organization_id)
        .order_by(Project.created_at.desc())
    )
    return list(result)


@router.get("/{project_id}", response_model=ProjectRead)
async def get_project(
    project_id: uuid.UUID,
    organization_id: OrganizationId,
    db: DbSession,
) -> Project:
    project = await db.scalar(
        select(Project).where(
            Project.id == project_id,
            Project.organization_id == organization_id,
        )
    )
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return project
