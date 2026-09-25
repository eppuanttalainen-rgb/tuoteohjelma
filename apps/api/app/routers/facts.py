import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.dependencies import OrganizationId, ReviewerId
from app.fact_extraction import (
    DeterministicFactExtractor,
    candidate_fingerprint,
    get_fact_extractor,
)
from app.models import Document, DocumentPage, FactCandidate, FactReview, Project
from app.schemas import (
    FactCandidateRead,
    FactExtractionResult,
    FactReviewCreate,
    FactReviewRead,
)

router = APIRouter(tags=["facts"])
DbSession = Annotated[AsyncSession, Depends(get_db)]
FactExtractor = Annotated[DeterministicFactExtractor, Depends(get_fact_extractor)]


async def _get_document(
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


async def _get_candidate(
    candidate_id: uuid.UUID,
    organization_id: uuid.UUID,
    db: AsyncSession,
) -> FactCandidate:
    candidate = await db.scalar(
        select(FactCandidate).where(
            FactCandidate.id == candidate_id,
            FactCandidate.organization_id == organization_id,
        )
    )
    if candidate is None:
        raise HTTPException(status_code=404, detail="Fact candidate not found")
    return candidate


@router.post(
    "/api/v1/documents/{document_id}/extract-facts",
    response_model=FactExtractionResult,
)
async def extract_document_facts(
    document_id: uuid.UUID,
    organization_id: OrganizationId,
    db: DbSession,
    extractor: FactExtractor,
) -> FactExtractionResult:
    document = await _get_document(document_id, organization_id, db)
    if document.processing_status != "PARSED":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Document must be PARSED before fact extraction",
        )

    pages_result = await db.scalars(
        select(DocumentPage)
        .where(
            DocumentPage.document_id == document.id,
            DocumentPage.organization_id == organization_id,
        )
        .order_by(DocumentPage.page_number.asc())
    )
    pages = list(pages_result)

    existing_result = await db.scalars(
        select(FactCandidate.candidate_fingerprint).where(
            FactCandidate.document_id == document.id,
            FactCandidate.organization_id == organization_id,
        )
    )
    existing_fingerprints = set(existing_result)

    created = 0
    existing = 0

    for page in pages:
        for fact in extractor.extract(page.text):
            fingerprint = candidate_fingerprint(
                page.id,
                fact,
                extractor.name,
                extractor.version,
            )
            if fingerprint in existing_fingerprints:
                existing += 1
                continue

            db.add(
                FactCandidate(
                    organization_id=organization_id,
                    project_id=document.project_id,
                    machine_id=document.machine_id,
                    document_id=document.id,
                    document_page_id=page.id,
                    fact_key=fact.fact_key,
                    raw_value=fact.raw_value,
                    normalized_value=fact.normalized_value,
                    unit=fact.unit,
                    confidence=fact.confidence,
                    source_excerpt=fact.source_excerpt,
                    extraction_method=extractor.name,
                    extraction_version=extractor.version,
                    candidate_fingerprint=fingerprint,
                    effective_date=fact.effective_date,
                    review_state="PROPOSED",
                )
            )
            existing_fingerprints.add(fingerprint)
            created += 1

    await db.commit()

    return FactExtractionResult(
        document_id=document.id,
        candidates_created=created,
        candidates_existing=existing,
        extraction_method=extractor.name,
        extraction_version=extractor.version,
    )


@router.get(
    "/api/v1/projects/{project_id}/fact-candidates",
    response_model=list[FactCandidateRead],
)
async def list_project_fact_candidates(
    project_id: uuid.UUID,
    organization_id: OrganizationId,
    db: DbSession,
) -> list[FactCandidate]:
    project = await db.scalar(
        select(Project).where(
            Project.id == project_id,
            Project.organization_id == organization_id,
        )
    )
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")

    result = await db.scalars(
        select(FactCandidate)
        .where(
            FactCandidate.project_id == project_id,
            FactCandidate.organization_id == organization_id,
        )
        .order_by(
            FactCandidate.fact_key.asc(),
            FactCandidate.created_at.asc(),
        )
    )
    return list(result)


@router.post(
    "/api/v1/fact-candidates/{candidate_id}/review",
    response_model=FactCandidateRead,
)
async def review_fact_candidate(
    candidate_id: uuid.UUID,
    payload: FactReviewCreate,
    organization_id: OrganizationId,
    reviewer_id: ReviewerId,
    db: DbSession,
) -> FactCandidate:
    candidate = await _get_candidate(candidate_id, organization_id, db)
    previous_state = candidate.review_state
    new_state = payload.action

    if payload.action == "CONFIRMED":
        candidate.reviewed_value = candidate.normalized_value
    elif payload.action == "CORRECTED":
        candidate.reviewed_value = payload.corrected_value
    else:
        candidate.reviewed_value = None

    candidate.review_state = new_state
    db.add(
        FactReview(
            organization_id=organization_id,
            candidate_id=candidate.id,
            action=payload.action,
            previous_state=previous_state,
            new_state=new_state,
            corrected_value=payload.corrected_value,
            note=payload.note,
            actor_reference=reviewer_id,
        )
    )
    await db.commit()
    await db.refresh(candidate)
    return candidate


@router.get(
    "/api/v1/fact-candidates/{candidate_id}/reviews",
    response_model=list[FactReviewRead],
)
async def list_fact_reviews(
    candidate_id: uuid.UUID,
    organization_id: OrganizationId,
    db: DbSession,
) -> list[FactReview]:
    candidate = await _get_candidate(candidate_id, organization_id, db)
    result = await db.scalars(
        select(FactReview)
        .where(
            FactReview.candidate_id == candidate.id,
            FactReview.organization_id == organization_id,
        )
        .order_by(FactReview.created_at.asc())
    )
    return list(result)
