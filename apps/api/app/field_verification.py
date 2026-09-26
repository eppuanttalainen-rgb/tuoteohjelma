import hashlib
import json
import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    FactCandidate,
    FactReview,
    StateAssertion,
    VerificationResult,
    VerificationTask,
)
from app.reconciliation import reconcile_project
from app.schemas import VerificationResultCreate, VerificationSubmissionResult


def _effective_candidate_value(candidate: FactCandidate) -> Any:
    if candidate.review_state == "CORRECTED":
        return candidate.reviewed_value
    return candidate.normalized_value


def _normalize_observed_value(
    observed_value: Any,
    peers: list[FactCandidate],
) -> Any:
    numeric_expected = any(
        isinstance(_effective_candidate_value(candidate), (int, float))
        and not isinstance(_effective_candidate_value(candidate), bool)
        for candidate in peers
    )

    if numeric_expected and isinstance(observed_value, str):
        raw = observed_value.strip().replace(",", ".")
        try:
            parsed = float(raw)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Observed value must be numeric for this fact",
            ) from exc
        return int(parsed) if parsed.is_integer() else parsed

    return observed_value


def _raw_value(value: Any) -> str:
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def _candidate_fingerprint(
    verification_result_id: uuid.UUID,
    fact_key: str,
    value: Any,
    unit: str | None,
) -> str:
    payload = json.dumps(
        {
            "verification_result_id": str(verification_result_id),
            "fact_key": fact_key,
            "value": value,
            "unit": unit,
            "method": "field_verification",
            "version": "v1",
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


async def submit_verification_result(
    db: AsyncSession,
    *,
    organization_id: uuid.UUID,
    task_id: uuid.UUID,
    reviewer_id: str,
    payload: VerificationResultCreate,
) -> VerificationSubmissionResult:
    task = await db.scalar(
        select(VerificationTask).where(
            VerificationTask.id == task_id,
            VerificationTask.organization_id == organization_id,
        )
    )
    if task is None:
        raise HTTPException(status_code=404, detail="Verification task not found")

    if task.reason_code == "MISSING_REFERENCED_DOCUMENT":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This task must be resolved by supplying the referenced document",
        )

    existing_result = await db.scalar(
        select(VerificationResult).where(
            VerificationResult.verification_task_id == task.id,
            VerificationResult.organization_id == organization_id,
        )
    )
    if existing_result is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Verification result already exists for this task",
        )

    if task.status != "OPEN":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Verification task is not open",
        )

    peer_result = await db.scalars(
        select(FactCandidate).where(
            FactCandidate.organization_id == organization_id,
            FactCandidate.machine_id == task.machine_id,
            FactCandidate.fact_key == task.fact_key,
        )
    )
    peers = list(peer_result)
    observed_value = _normalize_observed_value(payload.observed_value, peers)

    unit = payload.unit
    peer_units = {candidate.unit for candidate in peers if candidate.unit is not None}
    if unit is None and len(peer_units) == 1:
        unit = next(iter(peer_units))
    if task.reason_code == "UNIT_CONFLICT" and unit is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Unit is required to resolve a unit conflict",
        )

    now = datetime.now(UTC)
    verification = VerificationResult(
        organization_id=organization_id,
        project_id=task.project_id,
        verification_task_id=task.id,
        machine_id=task.machine_id,
        fact_key=task.fact_key,
        observed_value=observed_value,
        unit=unit,
        note=payload.note,
        photo_reference=payload.photo_reference,
        verified_by=reviewer_id,
        verified_at=now,
    )
    db.add(verification)
    await db.flush()

    raw_value = _raw_value(observed_value)
    candidate = FactCandidate(
        organization_id=organization_id,
        project_id=task.project_id,
        machine_id=task.machine_id,
        source_kind="FIELD_VERIFICATION",
        document_id=None,
        document_page_id=None,
        verification_result_id=verification.id,
        fact_key=task.fact_key,
        raw_value=raw_value,
        normalized_value=observed_value,
        unit=unit,
        confidence=1.0,
        source_excerpt=f"Field verification observed: {raw_value}",
        extraction_method="field_verification",
        extraction_version="v1",
        candidate_fingerprint=_candidate_fingerprint(
            verification.id,
            task.fact_key,
            observed_value,
            unit,
        ),
        effective_date=now.date(),
        review_state="PROPOSED",
    )
    db.add(candidate)
    await db.flush()

    candidate.review_state = "CONFIRMED"
    candidate.reviewed_value = observed_value
    db.add(
        FactReview(
            organization_id=organization_id,
            candidate_id=candidate.id,
            action="CONFIRMED",
            previous_state="PROPOSED",
            new_state="CONFIRMED",
            corrected_value=None,
            note=payload.note or "Confirmed by field verification.",
            actor_reference=reviewer_id,
        )
    )

    task.status = "RESOLVED"
    task.resolution_value = observed_value
    task.resolved_at = now

    await db.commit()
    await reconcile_project(
        db,
        organization_id=organization_id,
        project_id=task.project_id,
    )

    assertion = await db.scalar(
        select(StateAssertion).where(
            StateAssertion.organization_id == organization_id,
            StateAssertion.machine_id == task.machine_id,
            StateAssertion.fact_key == task.fact_key,
        )
    )

    await db.refresh(verification)
    return VerificationSubmissionResult(
        verification=verification,
        created_fact_candidate_id=candidate.id,
        state_assertion_id=assertion.id if assertion is not None else None,
    )
