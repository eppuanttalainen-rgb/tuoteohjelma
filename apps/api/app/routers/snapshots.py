import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.dependencies import OrganizationId, ReviewerId
from app.models import Machine, Snapshot
from app.reports import render_machine_evidence_report
from app.schemas import SnapshotRead, SnapshotSummary
from app.snapshots import create_or_get_snapshot

router = APIRouter(tags=["snapshots"])
DbSession = Annotated[AsyncSession, Depends(get_db)]


async def _get_machine(
    machine_id: uuid.UUID,
    organization_id: uuid.UUID,
    db: AsyncSession,
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


async def _get_snapshot(
    snapshot_id: uuid.UUID,
    organization_id: uuid.UUID,
    db: AsyncSession,
) -> Snapshot:
    snapshot = await db.scalar(
        select(Snapshot).where(
            Snapshot.id == snapshot_id,
            Snapshot.organization_id == organization_id,
        )
    )
    if snapshot is None:
        raise HTTPException(status_code=404, detail="Snapshot not found")
    return snapshot


@router.post(
    "/api/v1/machines/{machine_id}/snapshots",
    response_model=SnapshotRead,
)
async def create_snapshot(
    machine_id: uuid.UUID,
    organization_id: OrganizationId,
    reviewer_id: ReviewerId,
    db: DbSession,
) -> Snapshot:
    await _get_machine(machine_id, organization_id, db)
    return await create_or_get_snapshot(
        db,
        organization_id=organization_id,
        machine_id=machine_id,
        created_by=reviewer_id,
    )


@router.get(
    "/api/v1/machines/{machine_id}/snapshots",
    response_model=list[SnapshotSummary],
)
async def list_snapshots(
    machine_id: uuid.UUID,
    organization_id: OrganizationId,
    db: DbSession,
) -> list[Snapshot]:
    await _get_machine(machine_id, organization_id, db)
    result = await db.scalars(
        select(Snapshot)
        .where(
            Snapshot.organization_id == organization_id,
            Snapshot.machine_id == machine_id,
        )
        .order_by(Snapshot.created_at.desc())
    )
    return list(result)


@router.get(
    "/api/v1/snapshots/{snapshot_id}",
    response_model=SnapshotRead,
)
async def get_snapshot(
    snapshot_id: uuid.UUID,
    organization_id: OrganizationId,
    db: DbSession,
) -> Snapshot:
    return await _get_snapshot(snapshot_id, organization_id, db)


@router.get(
    "/api/v1/snapshots/{snapshot_id}/report",
    response_class=HTMLResponse,
)
async def get_snapshot_report(
    snapshot_id: uuid.UUID,
    organization_id: OrganizationId,
    db: DbSession,
) -> HTMLResponse:
    snapshot = await _get_snapshot(snapshot_id, organization_id, db)
    return HTMLResponse(
        content=render_machine_evidence_report(snapshot),
        headers={
            "Content-Disposition": (
                f'inline; filename="machine-evidence-{snapshot.state_hash[:12]}.html"'
            )
        },
    )
