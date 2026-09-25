import uuid
from pathlib import Path

from httpx import AsyncClient

from scripts.generate_golden_pack import generate_pack


async def _create_project_and_machine(
    client: AsyncClient,
    organization_id: str,
) -> tuple[dict, dict]:
    project_response = await client.post(
        "/api/v1/projects",
        headers={"X-Organization-Id": organization_id},
        json={
            "title": "Conveyor Line Retrofit - Test Rig Alpha",
            "jurisdiction": "EU",
        },
    )
    assert project_response.status_code == 201
    project = project_response.json()

    machine_response = await client.post(
        f"/api/v1/projects/{project['id']}/machines",
        headers={"X-Organization-Id": organization_id},
        json={
            "manufacturer": "Northfield Handling Systems",
            "model": "CV-204",
            "serial_number": "NHS-CV204-09117",
            "year": 2009,
            "machine_type": "belt_conveyor",
        },
    )
    assert machine_response.status_code == 201
    return project, machine_response.json()


async def _upload_parse_extract(
    client: AsyncClient,
    organization_id: str,
    project_id: str,
    path: Path,
    machine_id: str | None,
) -> tuple[dict, dict]:
    data = {"machine_id": machine_id} if machine_id else None
    upload = await client.post(
        f"/api/v1/projects/{project_id}/documents",
        headers={"X-Organization-Id": organization_id},
        data=data,
        files={"file": (path.name, path.read_bytes(), "application/pdf")},
    )
    assert upload.status_code == 201
    document = upload.json()

    parsed = await client.post(
        f"/api/v1/documents/{document['id']}/parse",
        headers={"X-Organization-Id": organization_id},
    )
    assert parsed.status_code == 200

    extracted = await client.post(
        f"/api/v1/documents/{document['id']}/extract-facts",
        headers={"X-Organization-Id": organization_id},
    )
    assert extracted.status_code == 200
    return document, extracted.json()


async def test_golden_fact_candidates_keep_conflicting_values_separate(
    client: AsyncClient,
    tmp_path: Path,
) -> None:
    organization_id = str(uuid.uuid4())
    reviewer_id = "dev-engineer"
    project, machine = await _create_project_and_machine(client, organization_id)
    pack_dir = tmp_path / "golden"
    generate_pack(pack_dir)

    uploaded: dict[str, dict] = {}
    machine_documents = {
        "01_oem_manual_2009.pdf",
        "02_motor_replacement_2021.pdf",
        "03_drive_replacement_2021.pdf",
        "04_safety_modification_2022.pdf",
        "05_plc_inventory.pdf",
        "07_guard_switch_field_note.pdf",
    }

    for filename in sorted(machine_documents | {"06_unrelated_motor_datasheet_7_5kw.pdf"}):
        document, extraction = await _upload_parse_extract(
            client,
            organization_id,
            project["id"],
            pack_dir / filename,
            machine["id"] if filename in machine_documents else None,
        )
        uploaded[filename] = document
        assert extraction["extraction_method"] == "deterministic_rules"
        assert extraction["extraction_version"] == "golden-v1"

    duplicate = await client.post(
        f"/api/v1/projects/{project['id']}/documents",
        headers={"X-Organization-Id": organization_id},
        files={
            "file": (
                "08_duplicate_oem_manual.pdf",
                (pack_dir / "08_duplicate_oem_manual.pdf").read_bytes(),
                "application/pdf",
            )
        },
    )
    assert duplicate.status_code == 409

    candidates_response = await client.get(
        f"/api/v1/projects/{project['id']}/fact-candidates",
        headers={"X-Organization-Id": organization_id},
    )
    assert candidates_response.status_code == 200
    candidates = candidates_response.json()
    assert candidates
    assert all(item["review_state"] == "PROPOSED" for item in candidates)

    motor_power_candidates = [
        item for item in candidates if item["fact_key"] == "motor.power_kw"
    ]
    values = [item["normalized_value"] for item in motor_power_candidates]
    assert values.count(11) == 2
    assert 15 in values
    assert 7.5 in values

    current_replacement = next(
        item
        for item in motor_power_candidates
        if item["normalized_value"] == 15
        and item["machine_id"] == machine["id"]
    )
    assert current_replacement["effective_date"] == "2021-06-14"
    assert current_replacement["source_excerpt"] == "Installed motor: 15 kW"

    unrelated = next(
        item for item in motor_power_candidates if item["normalized_value"] == 7.5
    )
    assert unrelated["machine_id"] is None
    assert unrelated["document_id"] == uploaded[
        "06_unrelated_motor_datasheet_7_5kw.pdf"
    ]["id"]

    confirm = await client.post(
        f"/api/v1/fact-candidates/{current_replacement['id']}/review",
        headers={
            "X-Organization-Id": organization_id,
            "X-Reviewer-Id": reviewer_id,
        },
        json={"action": "CONFIRMED", "note": "Matches the 2021 replacement record."},
    )
    assert confirm.status_code == 200
    assert confirm.json()["review_state"] == "CONFIRMED"
    assert confirm.json()["reviewed_value"] == 15

    guard_candidate = next(
        item
        for item in candidates
        if item["fact_key"] == "safety.guard_switch.model"
    )
    assert guard_candidate["normalized_value"] == "AZM ?"
    assert guard_candidate["confidence"] == 0.45

    correct = await client.post(
        f"/api/v1/fact-candidates/{guard_candidate['id']}/review",
        headers={
            "X-Organization-Id": organization_id,
            "X-Reviewer-Id": reviewer_id,
        },
        json={
            "action": "CORRECTED",
            "corrected_value": "AZM 161",
            "note": "Field verification result.",
        },
    )
    assert correct.status_code == 200
    assert correct.json()["review_state"] == "CORRECTED"
    assert correct.json()["reviewed_value"] == "AZM 161"
    assert correct.json()["normalized_value"] == "AZM ?"

    reject = await client.post(
        f"/api/v1/fact-candidates/{unrelated['id']}/review",
        headers={
            "X-Organization-Id": organization_id,
            "X-Reviewer-Id": reviewer_id,
        },
        json={
            "action": "REJECTED",
            "note": "Generic datasheet has no CV-204 asset reference.",
        },
    )
    assert reject.status_code == 200
    assert reject.json()["review_state"] == "REJECTED"
    assert reject.json()["reviewed_value"] is None

    reviews = await client.get(
        f"/api/v1/fact-candidates/{guard_candidate['id']}/reviews",
        headers={"X-Organization-Id": organization_id},
    )
    assert reviews.status_code == 200
    assert len(reviews.json()) == 1
    assert reviews.json()[0]["action"] == "CORRECTED"
    assert reviews.json()[0]["previous_state"] == "PROPOSED"
    assert reviews.json()[0]["new_state"] == "CORRECTED"
    assert reviews.json()[0]["actor_reference"] == reviewer_id
    assert reviews.json()[0]["corrected_value"] == "AZM 161"

    idempotent = await client.post(
        f"/api/v1/documents/{uploaded['02_motor_replacement_2021.pdf']['id']}/extract-facts",
        headers={"X-Organization-Id": organization_id},
    )
    assert idempotent.status_code == 200
    assert idempotent.json()["candidates_created"] == 0
    assert idempotent.json()["candidates_existing"] > 0

    locked_reparse = await client.post(
        f"/api/v1/documents/{uploaded['02_motor_replacement_2021.pdf']['id']}/parse",
        headers={"X-Organization-Id": organization_id},
    )
    assert locked_reparse.status_code == 409
    assert "provenance is locked" in locked_reparse.json()["detail"]


async def test_fact_candidate_tenant_boundary_and_review_validation(
    client: AsyncClient,
    tmp_path: Path,
) -> None:
    organization_a = str(uuid.uuid4())
    organization_b = str(uuid.uuid4())
    project, machine = await _create_project_and_machine(client, organization_a)
    pack_dir = tmp_path / "golden_second"
    generate_pack(pack_dir)

    await _upload_parse_extract(
        client,
        organization_a,
        project["id"],
        pack_dir / "02_motor_replacement_2021.pdf",
        machine["id"],
    )

    candidates = (
        await client.get(
            f"/api/v1/projects/{project['id']}/fact-candidates",
            headers={"X-Organization-Id": organization_a},
        )
    ).json()
    candidate = next(
        item
        for item in candidates
        if item["fact_key"] == "motor.power_kw"
        and item["normalized_value"] == 15
    )

    hidden = await client.get(
        f"/api/v1/projects/{project['id']}/fact-candidates",
        headers={"X-Organization-Id": organization_b},
    )
    assert hidden.status_code == 404

    denied_review = await client.post(
        f"/api/v1/fact-candidates/{candidate['id']}/review",
        headers={
            "X-Organization-Id": organization_b,
            "X-Reviewer-Id": "other-tenant",
        },
        json={"action": "CONFIRMED"},
    )
    assert denied_review.status_code == 404

    missing_correction = await client.post(
        f"/api/v1/fact-candidates/{candidate['id']}/review",
        headers={
            "X-Organization-Id": organization_a,
            "X-Reviewer-Id": "dev-engineer",
        },
        json={"action": "CORRECTED"},
    )
    assert missing_correction.status_code == 422
