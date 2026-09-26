import json
import uuid
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    Document,
    FactCandidate,
    StateAssertion,
    StateAssertionEvidence,
    VerificationTask,
)

DERIVATION_METHOD = "reviewed_fact_reconciliation"
DERIVATION_VERSION = "v1"

REVIEWED_STATES = {"CONFIRMED", "CORRECTED"}


def _effective_value(candidate: FactCandidate) -> Any:
    if candidate.review_state == "CORRECTED":
        return candidate.reviewed_value
    return candidate.normalized_value


def _value_key(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _is_ambiguous(candidate: FactCandidate) -> bool:
    if candidate.review_state == "CORRECTED":
        return False

    value = _effective_value(candidate)
    if candidate.confidence is not None and candidate.confidence < 0.5:
        return True
    if isinstance(value, str) and "?" in value:
        return True
    return False


def _derive_group(
    candidates: list[FactCandidate],
) -> tuple[str, Any | None, str | None, Any | None, dict[uuid.UUID, str], str | None]:
    units = {candidate.unit for candidate in candidates if candidate.unit is not None}
    if len(units) > 1:
        return (
            "DISPUTED",
            None,
            None,
            None,
            {candidate.id: "CONFLICTS" for candidate in candidates},
            "UNIT_CONFLICT",
        )

    if any(_is_ambiguous(candidate) for candidate in candidates):
        return (
            "UNKNOWN",
            None,
            next(iter(units), None),
            None,
            {candidate.id: "CONFLICTS" for candidate in candidates},
            "AMBIGUOUS_REVIEWED_VALUE",
        )

    values = {_value_key(_effective_value(candidate)) for candidate in candidates}
    unit = next(iter(units), None)

    if len(values) == 1:
        latest_date = max(
            (candidate.effective_date for candidate in candidates if candidate.effective_date),
            default=None,
        )
        value = _effective_value(candidates[0])
        return (
            "DERIVED",
            value,
            unit,
            latest_date,
            {candidate.id: "SUPPORTS" for candidate in candidates},
            None,
        )

    dated = [candidate for candidate in candidates if candidate.effective_date is not None]
    if len(dated) == len(candidates):
        latest_date = max(candidate.effective_date for candidate in dated)
        latest = [candidate for candidate in dated if candidate.effective_date == latest_date]
        latest_values = {_value_key(_effective_value(candidate)) for candidate in latest}

        if len(latest_values) == 1:
            winner_value = _effective_value(latest[0])
            relationships = {
                candidate.id: (
                    "SUPPORTS"
                    if candidate.effective_date == latest_date
                    and _value_key(_effective_value(candidate)) == _value_key(winner_value)
                    else "SUPERSEDED"
                )
                for candidate in candidates
            }
            return (
                "DERIVED",
                winner_value,
                unit,
                latest_date,
                relationships,
                None,
            )

    return (
        "DISPUTED",
        None,
        unit,
        None,
        {candidate.id: "CONFLICTS" for candidate in candidates},
        "CONFLICTING_REVIEWED_VALUES",
    )


async def _ensure_task(
    db: AsyncSession,
    *,
    organization_id: uuid.UUID,
    project_id: uuid.UUID,
    machine_id: uuid.UUID,
    fact_key: str,
    reason_code: str,
    reason: str,
    instructions: str,
) -> tuple[VerificationTask, bool]:
    task = await db.scalar(
        select(VerificationTask).where(
            VerificationTask.organization_id == organization_id,
            VerificationTask.machine_id == machine_id,
            VerificationTask.fact_key == fact_key,
            VerificationTask.reason_code == reason_code,
        )
    )
    opened = False

    if task is None:
        task = VerificationTask(
            organization_id=organization_id,
            project_id=project_id,
            machine_id=machine_id,
            fact_key=fact_key,
            reason_code=reason_code,
            reason=reason,
            instructions=instructions,
            status="OPEN",
        )
        db.add(task)
        opened = True
    else:
        if task.status != "OPEN":
            opened = True
        task.reason = reason
        task.instructions = instructions
        task.status = "OPEN"
        task.resolution_value = None
        task.resolved_at = None

    return task, opened


async def reconcile_project(
    db: AsyncSession,
    *,
    organization_id: uuid.UUID,
    project_id: uuid.UUID,
) -> dict[str, int | str | uuid.UUID]:
    reviewed_result = await db.scalars(
        select(FactCandidate).where(
            FactCandidate.organization_id == organization_id,
            FactCandidate.project_id == project_id,
            FactCandidate.review_state.in_(REVIEWED_STATES),
        )
    )
    reviewed = list(reviewed_result)

    grouped: dict[tuple[uuid.UUID, str], list[FactCandidate]] = defaultdict(list)
    for candidate in reviewed:
        if candidate.machine_id is None:
            continue
        grouped[(candidate.machine_id, candidate.fact_key)].append(candidate)

    existing_assertions_result = await db.scalars(
        select(StateAssertion).where(
            StateAssertion.organization_id == organization_id,
            StateAssertion.project_id == project_id,
        )
    )
    existing_assertions = {
        (assertion.machine_id, assertion.fact_key): assertion
        for assertion in existing_assertions_result
    }

    documents_result = await db.scalars(
        select(Document).where(
            Document.organization_id == organization_id,
            Document.project_id == project_id,
        )
    )
    documents = list(documents_result)
    supplied_filenames = {document.filename.lower() for document in documents}

    desired_assertion_keys: set[tuple[uuid.UUID, str]] = set()
    required_task_keys: set[tuple[uuid.UUID, str, str]] = set()

    derived = 0
    disputed = 0
    unknown = 0
    unchanged = 0
    tasks_opened = 0

    for (machine_id, fact_key), candidates in grouped.items():
        desired_assertion_keys.add((machine_id, fact_key))
        (
            status,
            value,
            unit,
            effective_date,
            relationships,
            reason_code,
        ) = _derive_group(candidates)

        assertion = existing_assertions.get((machine_id, fact_key))
        old_signature = None
        if assertion is not None:
            old_signature = (
                assertion.status,
                _value_key(assertion.value),
                assertion.unit,
                assertion.effective_date,
            )
        else:
            assertion = StateAssertion(
                organization_id=organization_id,
                project_id=project_id,
                machine_id=machine_id,
                fact_key=fact_key,
                status=status,
                value=value,
                unit=unit,
                derivation_method=DERIVATION_METHOD,
                derivation_version=DERIVATION_VERSION,
                effective_date=effective_date,
            )
            db.add(assertion)
            await db.flush()

        assertion.status = status
        assertion.value = value
        assertion.unit = unit
        assertion.derivation_method = DERIVATION_METHOD
        assertion.derivation_version = DERIVATION_VERSION
        assertion.effective_date = effective_date
        await db.flush()

        new_signature = (
            assertion.status,
            _value_key(assertion.value),
            assertion.unit,
            assertion.effective_date,
        )
        if old_signature == new_signature:
            unchanged += 1

        if status == "DERIVED":
            derived += 1
        elif status == "DISPUTED":
            disputed += 1
        elif status == "UNKNOWN":
            unknown += 1

        await db.execute(
            delete(StateAssertionEvidence).where(
                StateAssertionEvidence.assertion_id == assertion.id
            )
        )
        for candidate in candidates:
            db.add(
                StateAssertionEvidence(
                    organization_id=organization_id,
                    assertion_id=assertion.id,
                    fact_candidate_id=candidate.id,
                    relationship=relationships[candidate.id],
                )
            )

        if reason_code == "CONFLICTING_REVIEWED_VALUES":
            key = (machine_id, fact_key, reason_code)
            required_task_keys.add(key)
            _, opened = await _ensure_task(
                db,
                organization_id=organization_id,
                project_id=project_id,
                machine_id=machine_id,
                fact_key=fact_key,
                reason_code=reason_code,
                reason="Reviewed evidence contains different values without a clear chronology.",
                instructions=(
                    "Verify the current installed value in the field or provide dated evidence "
                    "that establishes which reviewed value is current."
                ),
            )
            tasks_opened += int(opened)

        if reason_code == "UNIT_CONFLICT":
            key = (machine_id, fact_key, reason_code)
            required_task_keys.add(key)
            _, opened = await _ensure_task(
                db,
                organization_id=organization_id,
                project_id=project_id,
                machine_id=machine_id,
                fact_key=fact_key,
                reason_code=reason_code,
                reason="Reviewed evidence uses incompatible units for the same fact.",
                instructions="Verify the engineering unit and normalize the reviewed value.",
            )
            tasks_opened += int(opened)

        if reason_code == "AMBIGUOUS_REVIEWED_VALUE":
            key = (machine_id, fact_key, reason_code)
            required_task_keys.add(key)
            _, opened = await _ensure_task(
                db,
                organization_id=organization_id,
                project_id=project_id,
                machine_id=machine_id,
                fact_key=fact_key,
                reason_code=reason_code,
                reason="Reviewed evidence still contains an incomplete or ambiguous value.",
                instructions=(
                    "Verify the exact value or model in the field and correct the fact candidate."
                ),
            )
            tasks_opened += int(opened)

        if fact_key == "evidence.reference.risk_assessment" and status == "DERIVED":
            reference = str(value).strip()
            reference_present = any(
                reference.lower() in filename for filename in supplied_filenames
            )
            if not reference_present:
                reason = "MISSING_REFERENCED_DOCUMENT"
                key = (machine_id, fact_key, reason)
                required_task_keys.add(key)
                _, opened = await _ensure_task(
                    db,
                    organization_id=organization_id,
                    project_id=project_id,
                    machine_id=machine_id,
                    fact_key=fact_key,
                    reason_code=reason,
                    reason=f"Reviewed evidence references {reference}, but that document is not supplied.",
                    instructions=(
                        f"Locate and upload {reference}, or record that the referenced document "
                        "cannot be obtained."
                    ),
                )
                tasks_opened += int(opened)

    stale_assertions = [
        assertion
        for key, assertion in existing_assertions.items()
        if key not in desired_assertion_keys
    ]
    for assertion in stale_assertions:
        await db.delete(assertion)

    tasks_result = await db.scalars(
        select(VerificationTask).where(
            VerificationTask.organization_id == organization_id,
            VerificationTask.project_id == project_id,
        )
    )
    tasks = list(tasks_result)
    tasks_resolved = 0

    assertion_value_map = {
        (assertion.machine_id, assertion.fact_key): assertion.value
        for assertion in list(existing_assertions.values())
        if (assertion.machine_id, assertion.fact_key) in desired_assertion_keys
    }

    for task in tasks:
        key = (task.machine_id, task.fact_key, task.reason_code)
        if key in required_task_keys:
            continue
        if task.status == "OPEN":
            task.status = "RESOLVED"
            task.resolved_at = datetime.now(timezone.utc)
            task.resolution_value = assertion_value_map.get(
                (task.machine_id, task.fact_key)
            )
            tasks_resolved += 1

    await db.commit()

    return {
        "project_id": project_id,
        "assertions_derived": derived,
        "assertions_disputed": disputed,
        "assertions_unknown": unknown,
        "assertions_unchanged": unchanged,
        "verification_tasks_opened": tasks_opened,
        "verification_tasks_resolved": tasks_resolved,
        "derivation_method": DERIVATION_METHOD,
        "derivation_version": DERIVATION_VERSION,
    }
