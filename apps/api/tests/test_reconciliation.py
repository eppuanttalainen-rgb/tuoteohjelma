import uuid
from pathlib import Path

from httpx import AsyncClient

from scripts.generate_golden_pack import generate_pack
from scripts.synthetic_pdf import make_text_pdf


async def _create_project_and_machine(
    client: AsyncClient,
    organization_id: str,
) -> tuple[dict, dict]:
    project_response = await client.post(
        "/api/v1/projects",
        headers={"X-Organization-Id": organization_id},
        json={"title": "CV-204 Slice 5", "jurisdiction": "EU"},
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
    *,
    filename: str,
    payload: bytes,
    machine_id: str | None,
) -> dict:
    data = {"machine_id": machine_id} if machine_id else None
    upload = await client.post(
        f"/api/v1/projects/{project_id}/documents",
        headers={"X-Organization-Id": organization_id},
        data=data,
        files={"file": (filename, payload, "application/pdf")},
    )
    assert upload.status_code == 201
    document = upload.json()

    parse = await client.post(
        f"/api/v1/documents/{document['id']}/parse",
        headers={"X-Organization-Id": organization_id},
    )
    assert parse.status_code == 200

    extraction = await client.post(
        f"/api/v1/documents/{document['id']}/extract-facts",
        headers={"X-Organization-Id": organization_id},
    )
    assert extraction.status_code == 200
    return document


async def _review(
    client: AsyncClient,
    organization_id: str,
    candidate_id: str,
    action: str,
    corrected_value=None,
) -> dict:
    body = {"action": action}
    if action == "CORRECTED":
        body["corrected_value"] = corrected_value

    response = await client.post(
        f"/api/v1/fact-candidates/{candidate_id}/review",
        headers={
            "X-Organization-Id": organization_id,
            "X-Reviewer-Id": "slice5-test-engineer",
        },
        json=body,
    )
    assert response.status_code == 200
    return response.json()


async def _candidates(
    client: AsyncClient,
    organization_id: str,
    project_id: str,
) -> list[dict]:
    response = await client.get(
        f"/api/v1/projects/{project_id}/fact-candidates",
        headers={"X-Organization-Id": organization_id},
    )
    assert response.status_code == 200
    return response.json()


async def test_cv204_chronology_and_verification_tasks(
    client: AsyncClient,
    tmp_path: Path,
) -> None:
    organization_id = str(uuid.uuid4())
    project, machine = await _create_project_and_machine(client, organization_id)
    pack = tmp_path / "golden_slice5"
    generate_pack(pack)

    for filename in [
        "01_oem_manual_2009.pdf",
        "02_motor_replacement_2021.pdf",
        "04_safety_modification_2022.pdf",
        "07_guard_switch_field_note.pdf",
    ]:
        await _upload_parse_extract(
            client,
            organization_id,
            project["id"],
            filename=filename,
            payload=(pack / filename).read_bytes(),
            machine_id=machine["id"],
        )

    unrelated_document = await _upload_parse_extract(
        client,
        organization_id,
        project["id"],
        filename="06_unrelated_motor_datasheet_7_5kw.pdf",
        payload=(pack / "06_unrelated_motor_datasheet_7_5kw.pdf").read_bytes(),
        machine_id=None,
    )

    candidates = await _candidates(client, organization_id, project["id"])

    original_11 = next(
        item
        for item in candidates
        if item["fact_key"] == "motor.power_kw"
        and item["normalized_value"] == 11
        and item["source_excerpt"] == "Rated power: 11 kW"
    )
    installed_15 = next(
        item
        for item in candidates
        if item["fact_key"] == "motor.power_kw"
        and item["normalized_value"] == 15
        and item["source_excerpt"] == "Installed motor: 15 kW"
    )
    unrelated_7_5 = next(
        item
        for item in candidates
        if item["fact_key"] == "motor.power_kw"
        and item["normalized_value"] == 7.5
        and item["document_id"] == unrelated_document["id"]
    )
    risk_reference = next(
        item
        for item in candidates
        if item["fact_key"] == "evidence.reference.risk_assessment"
    )
    ambiguous_guard = next(
        item
        for item in candidates
        if item["fact_key"] == "safety.guard_switch.model"
    )

    assert original_11["effective_date"] == "2009-01-01"
    assert installed_15["effective_date"] == "2021-06-14"
    assert unrelated_7_5["machine_id"] is None

    await _review(client, organization_id, original_11["id"], "CONFIRMED")
    await _review(client, organization_id, installed_15["id"], "CONFIRMED")
    await _review(client, organization_id, unrelated_7_5["id"], "CONFIRMED")
    await _review(client, organization_id, risk_reference["id"], "CONFIRMED")
    await _review(client, organization_id, ambiguous_guard["id"], "CONFIRMED")

    reconcile = await client.post(
        f"/api/v1/projects/{project['id']}/reconcile",
        headers={"X-Organization-Id": organization_id},
    )
    assert reconcile.status_code == 200
    result = reconcile.json()
    assert result["assertions_derived"] >= 2
    assert result["assertions_unknown"] >= 1
    assert result["verification_tasks_opened"] == 2

    assertions_response = await client.get(
        f"/api/v1/projects/{project['id']}/state-assertions",
        headers={"X-Organization-Id": organization_id},
    )
    assert assertions_response.status_code == 200
    assertions = assertions_response.json()

    motor_state = next(
        item for item in assertions if item["fact_key"] == "motor.power_kw"
    )
    assert motor_state["status"] == "DERIVED"
    assert motor_state["value"] == 15
    assert motor_state["unit"] == "kW"
    assert motor_state["effective_date"] == "2021-06-14"

    motor_detail = await client.get(
        f"/api/v1/state-assertions/{motor_state['id']}",
        headers={"X-Organization-Id": organization_id},
    )
    assert motor_detail.status_code == 200
    relationships = {
        item["fact_candidate_id"]: item["relationship"]
        for item in motor_detail.json()["evidence"]
    }
    assert relationships[installed_15["id"]] == "SUPPORTS"
    assert relationships[original_11["id"]] == "SUPERSEDED"
    assert unrelated_7_5["id"] not in relationships

    guard_state = next(
        item
        for item in assertions
        if item["fact_key"] == "safety.guard_switch.model"
    )
    assert guard_state["status"] == "UNKNOWN"
    assert guard_state["value"] is None

    tasks_response = await client.get(
        f"/api/v1/projects/{project['id']}/verification-tasks",
        headers={"X-Organization-Id": organization_id},
    )
    assert tasks_response.status_code == 200
    tasks = tasks_response.json()
    open_reasons = {
        task["reason_code"]
        for task in tasks
        if task["status"] == "OPEN"
    }
    assert open_reasons == {
        "AMBIGUOUS_REVIEWED_VALUE",
        "MISSING_REFERENCED_DOCUMENT",
    }

    await _review(
        client,
        organization_id,
        ambiguous_guard["id"],
        "CORRECTED",
        corrected_value="AZM 161",
    )

    risk_pdf = make_text_pdf(
        [
            "RISK ASSESSMENT\n"
            "Reference: RA-2022-17\n"
            "Machine: CV-204"
        ]
    )
    upload_risk = await client.post(
        f"/api/v1/projects/{project['id']}/documents",
        headers={"X-Organization-Id": organization_id},
        data={"machine_id": machine["id"]},
        files={"file": ("RA-2022-17.pdf", risk_pdf, "application/pdf")},
    )
    assert upload_risk.status_code == 201

    second_reconcile = await client.post(
        f"/api/v1/projects/{project['id']}/reconcile",
        headers={"X-Organization-Id": organization_id},
    )
    assert second_reconcile.status_code == 200
    second_result = second_reconcile.json()
    assert second_result["verification_tasks_resolved"] == 2

    assertions = (
        await client.get(
            f"/api/v1/projects/{project['id']}/state-assertions",
            headers={"X-Organization-Id": organization_id},
        )
    ).json()
    corrected_guard_state = next(
        item
        for item in assertions
        if item["fact_key"] == "safety.guard_switch.model"
    )
    assert corrected_guard_state["status"] == "DERIVED"
    assert corrected_guard_state["value"] == "AZM 161"

    tasks = (
        await client.get(
            f"/api/v1/projects/{project['id']}/verification-tasks",
            headers={"X-Organization-Id": organization_id},
        )
    ).json()
    assert all(task["status"] == "RESOLVED" for task in tasks)

    idempotent = await client.post(
        f"/api/v1/projects/{project['id']}/reconcile",
        headers={"X-Organization-Id": organization_id},
    )
    assert idempotent.status_code == 200
    assert idempotent.json()["verification_tasks_opened"] == 0
    assert idempotent.json()["verification_tasks_resolved"] == 0
    assert idempotent.json()["assertions_unchanged"] == len(assertions)


async def test_ambiguous_chronology_becomes_disputed(
    client: AsyncClient,
) -> None:
    organization_id = str(uuid.uuid4())
    project, machine = await _create_project_and_machine(client, organization_id)

    for filename, plc in [
        ("plc_a.pdf", "Siemens S7-300"),
        ("plc_b.pdf", "Siemens S7-1500"),
    ]:
        await _upload_parse_extract(
            client,
            organization_id,
            project["id"],
            filename=filename,
            payload=make_text_pdf(
                [
                    "CONTROL INVENTORY\n"
                    "Machine: CV-204\n"
                    f"PLC platform: {plc}"
                ]
            ),
            machine_id=machine["id"],
        )

    candidates = await _candidates(client, organization_id, project["id"])
    plc_candidates = [
        item for item in candidates if item["fact_key"] == "plc.platform"
    ]
    assert len(plc_candidates) == 2
    assert all(item["effective_date"] is None for item in plc_candidates)

    for candidate in plc_candidates:
        await _review(client, organization_id, candidate["id"], "CONFIRMED")

    reconcile = await client.post(
        f"/api/v1/projects/{project['id']}/reconcile",
        headers={"X-Organization-Id": organization_id},
    )
    assert reconcile.status_code == 200
    assert reconcile.json()["assertions_disputed"] == 1
    assert reconcile.json()["verification_tasks_opened"] == 1

    assertions = (
        await client.get(
            f"/api/v1/projects/{project['id']}/state-assertions",
            headers={"X-Organization-Id": organization_id},
        )
    ).json()
    plc_state = next(item for item in assertions if item["fact_key"] == "plc.platform")
    assert plc_state["status"] == "DISPUTED"
    assert plc_state["value"] is None

    detail = await client.get(
        f"/api/v1/state-assertions/{plc_state['id']}",
        headers={"X-Organization-Id": organization_id},
    )
    assert detail.status_code == 200
    assert {item["relationship"] for item in detail.json()["evidence"]} == {
        "CONFLICTS"
    }

    tasks = (
        await client.get(
            f"/api/v1/projects/{project['id']}/verification-tasks",
            headers={"X-Organization-Id": organization_id},
        )
    ).json()
    open_task = next(task for task in tasks if task["status"] == "OPEN")
    assert open_task["reason_code"] == "CONFLICTING_REVIEWED_VALUES"
    assert open_task["fact_key"] == "plc.platform"

    hidden = await client.get(
        f"/api/v1/projects/{project['id']}/state-assertions",
        headers={"X-Organization-Id": str(uuid.uuid4())},
    )
    assert hidden.status_code == 404
