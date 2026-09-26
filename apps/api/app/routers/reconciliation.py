import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.dependencies import OrganizationId
from app.models import (
    Project,
    StateAssertion,
    StateAssertionEvidence,
    VerificationTask,
)
from app.reconciliation import reconcile_project
from app.schemas import (
    AssertionEvidenceRead,
    ReconciliationResult,
    StateAssertionDetail,
    StateAssertionRead,
    VerificationTaskRead,
)

router = APIRouter(tags=["reconciliation"])
DbSession = Annotated[AsyncSession, Depends(get_db)]


async def _get_project(
    project_id: uuid.UUID,
    organization_id: uuid.UUID,
    db: AsyncSession,
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


@router.post(
    "/api/v1/projects/{project_id}/reconcile",
    response_model=ReconciliationResult,
)
async def reconcile(
    project_id: uuid.UUID,
    organization_id: OrganizationId,
    db: DbSession,
) -> ReconciliationResult:
    await _get_project(project_id, organization_id, db)
    result = await reconcile_project(
        db,
        organization_id=organization_id,
        project_id=project_id,
    )
    return ReconciliationResult(**result)


@router.get(
    "/api/v1/projects/{project_id}/state-assertions",
    response_model=list[StateAssertionRead],
)
async def list_state_assertions(
    project_id: uuid.UUID,
    organization_id: OrganizationId,
    db: DbSession,
) -> list[StateAssertion]:
    await _get_project(project_id, organization_id, db)
    result = await db.scalars(
        select(StateAssertion)
        .where(
            StateAssertion.project_id == project_id,
            StateAssertion.organization_id == organization_id,
        )
        .order_by(StateAssertion.fact_key.asc())
    )
    return list(result)


@router.get(
    "/api/v1/state-assertions/{assertion_id}",
    response_model=StateAssertionDetail,
)
async def get_state_assertion(
    assertion_id: uuid.UUID,
    organization_id: OrganizationId,
    db: DbSession,
) -> StateAssertionDetail:
    assertion = await db.scalar(
        select(StateAssertion).where(
            StateAssertion.id == assertion_id,
            StateAssertion.organization_id == organization_id,
        )
    )
    if assertion is None:
        raise HTTPException(status_code=404, detail="State assertion not found")

    evidence_result = await db.scalars(
        select(StateAssertionEvidence)
        .where(
            StateAssertionEvidence.assertion_id == assertion.id,
            StateAssertionEvidence.organization_id == organization_id,
        )
        .order_by(StateAssertionEvidence.created_at.asc())
    )
    evidence = [
        AssertionEvidenceRead.model_validate(item)
        for item in evidence_result
    ]
    return StateAssertionDetail(
        **StateAssertionRead.model_validate(assertion).model_dump(),
        evidence=evidence,
    )


@router.get(
    "/api/v1/projects/{project_id}/verification-tasks",
    response_model=list[VerificationTaskRead],
)
async def list_verification_tasks(
    project_id: uuid.UUID,
    organization_id: OrganizationId,
    db: DbSession,
) -> list[VerificationTask]:
    await _get_project(project_id, organization_id, db)
    result = await db.scalars(
        select(VerificationTask)
        .where(
            VerificationTask.project_id == project_id,
            VerificationTask.organization_id == organization_id,
        )
        .order_by(
            VerificationTask.status.asc(),
            VerificationTask.created_at.asc(),
        )
    )
    return list(result)
