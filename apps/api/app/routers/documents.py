import uuid
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.dependencies import OrganizationId
from app.models import Document, DocumentPage, Machine, Project
from app.parsing import PdfParseError, PypdfParser, get_pdf_parser
from app.schemas import DocumentPageRead, DocumentParseResult, DocumentRead
from app.storage import (
    EvidenceTooLargeError,
    InvalidStorageKeyError,
    LocalObjectStorage,
    get_storage,
)

router = APIRouter(tags=["documents"])
DbSession = Annotated[AsyncSession, Depends(get_db)]
Storage = Annotated[LocalObjectStorage, Depends(get_storage)]
PdfParser = Annotated[PypdfParser, Depends(get_pdf_parser)]


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


async def _get_document_record(
    document_id: uuid.UUID,
    organization_id: uuid.UUID,
    db: AsyncSession,
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
    file: Annotated[UploadFile, File()],
    machine_id: Annotated[uuid.UUID | None, Form()] = None,
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
    except Exception:
        await db.rollback()
        storage.delete(stored.key)
        raise

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
    return await _get_document_record(document_id, organization_id, db)


@router.post(
    "/api/v1/documents/{document_id}/parse",
    response_model=DocumentParseResult,
)
async def parse_document(
    document_id: uuid.UUID,
    organization_id: OrganizationId,
    db: DbSession,
    storage: Storage,
    parser: PdfParser,
) -> DocumentParseResult:
    document = await _get_document_record(document_id, organization_id, db)

    if document.processing_status == "PARSING":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Document is already being parsed",
        )

    document.processing_status = "PARSING"
    await db.commit()

    try:
        pdf_bytes = storage.read_bytes(document.storage_key)
        parsed_pages = parser.parse(pdf_bytes)
    except (FileNotFoundError, InvalidStorageKeyError, PdfParseError) as exc:
        document.processing_status = "PARSE_FAILED"
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Evidence could not be parsed",
        ) from exc

    try:
        await db.execute(
            delete(DocumentPage).where(DocumentPage.document_id == document.id)
        )
        for page in parsed_pages:
            db.add(
                DocumentPage(
                    organization_id=organization_id,
                    document_id=document.id,
                    page_number=page.page_number,
                    text=page.text,
                    text_sha256=page.text_sha256,
                    parser_name=parser.name,
                    parser_version=parser.version,
                )
            )

        document.processing_status = "PARSED"
        await db.commit()
    except Exception:
        await db.rollback()
        document.processing_status = "PARSE_FAILED"
        await db.commit()
        raise

    return DocumentParseResult(
        document_id=document.id,
        processing_status=document.processing_status,
        page_count=len(parsed_pages),
        parser_name=parser.name,
        parser_version=parser.version,
    )


@router.get(
    "/api/v1/documents/{document_id}/pages",
    response_model=list[DocumentPageRead],
)
async def list_document_pages(
    document_id: uuid.UUID,
    organization_id: OrganizationId,
    db: DbSession,
) -> list[DocumentPage]:
    await _get_document_record(document_id, organization_id, db)
    result = await db.scalars(
        select(DocumentPage)
        .where(
            DocumentPage.document_id == document_id,
            DocumentPage.organization_id == organization_id,
        )
        .order_by(DocumentPage.page_number.asc())
    )
    return list(result)
