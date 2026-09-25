import uuid
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.dependencies import OrganizationId
from app.models import Document, Machine, Project
from app.schemas import DocumentRead
from app.storage import EvidenceTooLargeError, LocalObjectStorage, get_storage

router = APIRouter(tags=["documents"])
DbSession = Annotated[AsyncSession, Depends(get_db)]
Storage = Annotated[LocalObjectStorage, Depends(get_storage)]


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
    "/api/v1/projects/{project_id}/documents",
    response_model=DocumentRead,
    status_code=status.HTTP_201_CREATED,
)
async def upload_document(
    project_id: uuid.UUID,
    organization_id: OrganizationId,
    db: DbSession,
    storage: Storage,
    file: UploadFile = File(...),
    machine_id: uuid.UUID | None = Form(default=None),
) -> Document:
    await _get_project(project_id, organization_id, db)

    if machine_id is not None:
        machine = await db.scalar(
            select(Machine).where(
                Machine.id == machine_id,
                Machine.project_id == project_id,
                Machine.organization_id == organization_id,
            )
        )
        if machine is None:
            raise HTTPException(status_code=404, detail="Machine not found")

    if file.content_type != "application/pdf":
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Only PDF evidence is supported in Slice 2",
        )

    signature = await file.read(5)
    await file.seek(0)
    if signature != b"%PDF-":
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Uploaded file does not have a valid PDF signature",
        )

    try:
        stored = await storage.save(file, organization_id, project_id)
    except EvidenceTooLargeError as exc:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=str(exc),
        ) from exc

    existing = await db.scalar(
        select(Document).where(
            Document.organization_id == organization_id,
            Document.project_id == project_id,
            Document.sha256 == stored.sha256,
        )
    )
    if existing is not None:
        storage.delete(stored.key)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "message": "Duplicate evidence file",
                "existing_document_id": str(existing.id),
            },
        )

    document = Document(
        organization_id=organization_id,
        project_id=project_id,
        machine_id=machine_id,
        filename=Path(file.filename or "evidence.pdf").name,
        content_type=file.content_type,
        size_bytes=stored.size_bytes,
        storage_key=stored.key,
        sha256=stored.sha256,
        processing_status="STORED",
    )
    db.add(document)

    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        storage.delete(stored.key)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Duplicate evidence file",
        ) from exc

    await db.refresh(document)
    return document


@router.get(
    "/api/v1/projects/{project_id}/documents",
    response_model=list[DocumentRead],
)
async def list_documents(
    project_id: uuid.UUID,
    organization_id: OrganizationId,
    db: DbSession,
) -> list[Document]:
    await _get_project(project_id, organization_id, db)
    result = await db.scalars(
        select(Document)
        .where(
            Document.project_id == project_id,
            Document.organization_id == organization_id,
        )
        .order_by(Document.created_at.desc())
    )
    return list(result)


@router.get("/api/v1/documents/{document_id}", response_model=DocumentRead)
async def get_document(
    document_id: uuid.UUID,
    organization_id: OrganizationId,
    db: DbSession,
) -> Document:
    document = await db.scalar(
        select(Document).where(
            Document.id == document_id,
            Document.organization_id == organization_id,
        )
    )
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")
    return document
