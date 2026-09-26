import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.dependencies import OrganizationId, ReviewerId
from app.field_verification import submit_verification_result
from app.models import VerificationResult, VerificationTask
from app.schemas import (
    VerificationResultCreate,
    VerificationResultRead,
    VerificationSubmissionResult,
    VerificationTaskRead,
)

router = APIRouter(tags=["verification"])
DbSession = Annotated[AsyncSession, Depends(get_db)]


async def _get_task(
    task_id: uuid.UUID,
    organization_id: uuid.UUID,
    db: AsyncSession,
) -> VerificationTask:
    task = await db.scalar(
        select(VerificationTask).where(
            VerificationTask.id == task_id,
            VerificationTask.organization_id == organization_id,
        )
    )
    if task is None:
        raise HTTPException(status_code=404, detail="Verification task not found")
    return task


@router.get(
    "/api/v1/verification-tasks/{task_id}",
    response_model=VerificationTaskRead,
)
async def get_verification_task(
    task_id: uuid.UUID,
    organization_id: OrganizationId,
    db: DbSession,
) -> VerificationTask:
    return await _get_task(task_id, organization_id, db)


@router.post(
    "/api/v1/verification-tasks/{task_id}/verify",
    response_model=VerificationSubmissionResult,
)
async def verify_task(
    task_id: uuid.UUID,
    payload: VerificationResultCreate,
    organization_id: OrganizationId,
    reviewer_id: ReviewerId,
    db: DbSession,
) -> VerificationSubmissionResult:
    return await submit_verification_result(
        db,
        organization_id=organization_id,
        task_id=task_id,
        reviewer_id=reviewer_id,
        payload=payload,
    )


@router.get(
    "/api/v1/verification-tasks/{task_id}/result",
    response_model=VerificationResultRead,
)
async def get_verification_result(
    task_id: uuid.UUID,
    organization_id: OrganizationId,
    db: DbSession,
) -> VerificationResult:
    await _get_task(task_id, organization_id, db)
    result = await db.scalar(
        select(VerificationResult).where(
            VerificationResult.verification_task_id == task_id,
            VerificationResult.organization_id == organization_id,
        )
    )
    if result is None:
        raise HTTPException(status_code=404, detail="Verification result not found")
    return result
