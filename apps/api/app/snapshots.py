import hashlib
import json
import uuid
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    Document,
    FactCandidate,
    Machine,
    Project,
    Snapshot,
    StateAssertion,
    StateAssertionEvidence,
    VerificationResult,
    VerificationTask,
)

SNAPSHOT_TYPE = "CURRENT_STATE_BASELINE"
SNAPSHOT_SCHEMA_VERSION = "1.0"


def _canonical_hash(payload: dict[str, Any]) -> str:
    canonical = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _json_value(value: Any) -> Any:
    return value


def _candidate_value(candidate: FactCandidate) -> Any:
    if candidate.review_state == "CORRECTED":
        return candidate.reviewed_value
    return candidate.normalized_value


async def build_snapshot_payload(
    db: AsyncSession,
    *,
    organization_id: uuid.UUID,
    machine_id: uuid.UUID,
) -> tuple[Project, Machine, dict[str, Any]]:
    machine = await db.scalar(
        select(Machine).where(
            Machine.id == machine_id,
            Machine.organization_id == organization_id,
        )
    )
    if machine is None:
        raise HTTPException(status_code=404, detail="Machine not found")

    project = await db.scalar(
        select(Project).where(
            Project.id == machine.project_id,
            Project.organization_id == organization_id,
        )
    )
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")

    assertion_result = await db.scalars(
        select(StateAssertion)
        .where(
            StateAssertion.organization_id == organization_id,
            StateAssertion.machine_id == machine_id,
        )
        .order_by(StateAssertion.fact_key.asc())
    )
    assertions = list(assertion_result)
    if not assertions:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Reconcile reviewed facts before creating a snapshot",
        )

    assertion_ids = [assertion.id for assertion in assertions]
    evidence_result = await db.scalars(
        select(StateAssertionEvidence)
        .where(
            StateAssertionEvidence.organization_id == organization_id,
            StateAssertionEvidence.assertion_id.in_(assertion_ids),
        )
        .order_by(
            StateAssertionEvidence.assertion_id.asc(),
            StateAssertionEvidence.relationship.asc(),
            StateAssertionEvidence.fact_candidate_id.asc(),
        )
    )
    evidence_links = list(evidence_result)

    candidate_ids = sorted(
        {link.fact_candidate_id for link in evidence_links},
        key=str,
    )
    candidates: list[FactCandidate] = []
    if candidate_ids:
        candidate_result = await db.scalars(
            select(FactCandidate).where(
                FactCandidate.organization_id == organization_id,
                FactCandidate.id.in_(candidate_ids),
            )
        )
        candidates = list(candidate_result)
    candidate_by_id = {candidate.id: candidate for candidate in candidates}

    links_by_assertion: dict[uuid.UUID, list[StateAssertionEvidence]] = {}
    for link in evidence_links:
        links_by_assertion.setdefault(link.assertion_id, []).append(link)

    assertion_payload: list[dict[str, Any]] = []
    for assertion in assertions:
        evidence_payload: list[dict[str, Any]] = []
        for link in sorted(
            links_by_assertion.get(assertion.id, []),
            key=lambda item: (item.relationship, str(item.fact_candidate_id)),
        ):
            candidate = candidate_by_id.get(link.fact_candidate_id)
            if candidate is None:
                continue
            evidence_payload.append(
                {
                    "relationship": link.relationship,
                    "candidate_id": str(candidate.id),
                    "fact_key": candidate.fact_key,
                    "value": _json_value(_candidate_value(candidate)),
                    "unit": candidate.unit,
                    "review_state": candidate.review_state,
                    "source_kind": candidate.source_kind,
                    "document_id": (
                        str(candidate.document_id)
                        if candidate.document_id is not None
                        else None
                    ),
                    "document_page_id": (
                        str(candidate.document_page_id)
                        if candidate.document_page_id is not None
                        else None
                    ),
                    "verification_result_id": (
                        str(candidate.verification_result_id)
                        if candidate.verification_result_id is not None
                        else None
                    ),
                    "source_excerpt": candidate.source_excerpt,
                    "effective_date": (
                        candidate.effective_date.isoformat()
                        if candidate.effective_date is not None
                        else None
                    ),
                    "extraction_method": candidate.extraction_method,
                    "extraction_version": candidate.extraction_version,
                }
            )

        assertion_payload.append(
            {
                "fact_key": assertion.fact_key,
                "value": _json_value(assertion.value),
                "unit": assertion.unit,
                "status": assertion.status,
                "effective_date": (
                    assertion.effective_date.isoformat()
                    if assertion.effective_date is not None
                    else None
                ),
                "derivation_method": assertion.derivation_method,
                "derivation_version": assertion.derivation_version,
                "evidence": evidence_payload,
            }
        )

    document_result = await db.scalars(
        select(Document)
        .where(
            Document.organization_id == organization_id,
            Document.project_id == project.id,
            or_(Document.machine_id == machine_id, Document.machine_id.is_(None)),
        )
        .order_by(Document.filename.asc(), Document.sha256.asc())
    )
    documents = [
        {
            "document_id": str(document.id),
            "filename": document.filename,
            "machine_id": (
                str(document.machine_id) if document.machine_id is not None else None
            ),
            "sha256": document.sha256,
            "size_bytes": document.size_bytes,
            "content_type": document.content_type,
            "document_type": document.document_type,
            "revision": document.revision,
            "document_date": (
                document.document_date.isoformat()
                if document.document_date is not None
                else None
            ),
            "language": document.language,
            "processing_status": document.processing_status,
        }
        for document in document_result
    ]

    task_result = await db.scalars(
        select(VerificationTask)
        .where(
            VerificationTask.organization_id == organization_id,
            VerificationTask.machine_id == machine_id,
        )
        .order_by(
            VerificationTask.status.asc(),
            VerificationTask.fact_key.asc(),
            VerificationTask.reason_code.asc(),
        )
    )
    tasks = list(task_result)

    result_rows = await db.scalars(
        select(VerificationResult)
        .where(
            VerificationResult.organization_id == organization_id,
            VerificationResult.machine_id == machine_id,
        )
        .order_by(VerificationResult.verified_at.asc(), VerificationResult.id.asc())
    )
    results = list(result_rows)
    result_by_task = {result.verification_task_id: result for result in results}

    verification_payload = []
    for task in tasks:
        result = result_by_task.get(task.id)
        verification_payload.append(
            {
                "task_id": str(task.id),
                "fact_key": task.fact_key,
                "reason_code": task.reason_code,
                "reason": task.reason,
                "instructions": task.instructions,
                "status": task.status,
                "resolution_value": _json_value(task.resolution_value),
                "result": (
                    {
                        "verification_result_id": str(result.id),
                        "observed_value": _json_value(result.observed_value),
                        "unit": result.unit,
                        "note": result.note,
                        "photo_reference": result.photo_reference,
                        "verified_by": result.verified_by,
                        "verified_at": result.verified_at.isoformat(),
                    }
                    if result is not None
                    else None
                ),
            }
        )

    payload = {
        "schema_version": SNAPSHOT_SCHEMA_VERSION,
        "snapshot_type": SNAPSHOT_TYPE,
        "project": {
            "project_id": str(project.id),
            "title": project.title,
            "customer_reference": project.customer_reference,
            "objective": project.objective,
            "jurisdiction": project.jurisdiction,
            "status": project.status,
        },
        "machine": {
            "machine_id": str(machine.id),
            "manufacturer": machine.manufacturer,
            "model": machine.model,
            "serial_number": machine.serial_number,
            "year": machine.year,
            "internal_asset_id": machine.internal_asset_id,
            "machine_type": machine.machine_type,
            "status": machine.status,
        },
        "state_assertions": assertion_payload,
        "verification_tasks": verification_payload,
        "documents": documents,
    }
    return project, machine, payload


async def create_or_get_snapshot(
    db: AsyncSession,
    *,
    organization_id: uuid.UUID,
    machine_id: uuid.UUID,
    created_by: str,
) -> Snapshot:
    project, machine, payload = await build_snapshot_payload(
        db,
        organization_id=organization_id,
        machine_id=machine_id,
    )
    state_hash = _canonical_hash(payload)

    existing = await db.scalar(
        select(Snapshot).where(
            Snapshot.organization_id == organization_id,
            Snapshot.machine_id == machine.id,
            Snapshot.state_hash == state_hash,
        )
    )
    if existing is not None:
        return existing

    has_open_items = any(
        assertion["status"] in {"DISPUTED", "UNKNOWN"}
        for assertion in payload["state_assertions"]
    ) or any(
        task["status"] == "OPEN"
        for task in payload["verification_tasks"]
    )

    snapshot = Snapshot(
        organization_id=organization_id,
        project_id=project.id,
        machine_id=machine.id,
        snapshot_type=SNAPSHOT_TYPE,
        status="WITH_OPEN_ITEMS" if has_open_items else "REVIEWED_BASELINE",
        schema_version=SNAPSHOT_SCHEMA_VERSION,
        state_hash=state_hash,
        payload=payload,
        created_by=created_by,
    )
    db.add(snapshot)
    await db.commit()
    await db.refresh(snapshot)
    return snapshot
