import uuid

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
        json={"title": "CV-204 Field Verification", "jurisdiction": "EU"},
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
        },
    )
    assert machine_response.status_code == 201
    return project, machine_response.json()


async def _upload_parse_extract(
    client: AsyncClient,
    organization_id: str,
    project_id: str,
    machine_id: str,
    filename: str,
    payload: bytes,
) -> None:
    upload = await client.post(
        f"/api/v1/projects/{project_id}/documents",
        headers={"X-Organization-Id": organization_id},
        data={"machine_id": machine_id},
        files={"file": (filename, payload, "application/pdf")},
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


async def _confirm(
    client: AsyncClient,
    organization_id: str,
    candidate_id: str,
) -> None:
    response = await client.post(
        f"/api/v1/fact-candidates/{candidate_id}/review",
        headers={
            "X-Organization-Id": organization_id,
            "X-Reviewer-Id": "field-test-engineer",
        },
        json={"action": "CONFIRMED"},
    )
    assert response.status_code == 200


async def test_field_verification_resolves_ambiguous_guard_switch(
    client: AsyncClient,
    tmp_path,
) -> None:
    organization_id = str(uuid.uuid4())
    project, machine = await _create_project_and_machine(client, organization_id)
    pack = tmp_path / "golden_field"
    generate_pack(pack)

    await _upload_parse_extract(
        client,
        organization_id,
        project["id"],
        machine["id"],
        "07_guard_switch_field_note.pdf",
        (pack / "07_guard_switch_field_note.pdf").read_bytes(),
    )

    candidates = await _candidates(client, organization_id, project["id"])
    ambiguous = next(
        item
        for item in candidates
        if item["fact_key"] == "safety.guard_switch.model"
    )
    assert ambiguous["source_kind"] == "DOCUMENT_PAGE"
    assert ambiguous["document_id"] is not None
    assert ambiguous["document_page_id"] is not None
    assert ambiguous["verification_result_id"] is None

    await _confirm(client, organization_id, ambiguous["id"])

    reconcile = await client.post(
        f"/api/v1/projects/{project['id']}/reconcile",
        headers={"X-Organization-Id": organization_id},
    )
    assert reconcile.status_code == 200

    tasks = (
        await client.get(
            f"/api/v1/projects/{project['id']}/verification-tasks",
            headers={"X-Organization-Id": organization_id},
        )
    ).json()
    task = next(
        item
        for item in tasks
        if item["reason_code"] == "AMBIGUOUS_REVIEWED_VALUE"
        and item["status"] == "OPEN"
    )

    submitted = await client.post(
        f"/api/v1/verification-tasks/{task['id']}/verify",
        headers={
            "X-Organization-Id": organization_id,
            "X-Reviewer-Id": "field-engineer",
        },
        json={
            "observed_value": "AZM 161",
            "note": "Label read directly from installed guard switch.",
        },
    )
    assert submitted.status_code == 200
    submission = submitted.json()
    assert submission["verification"]["observed_value"] == "AZM 161"
    assert submission["verification"]["verified_by"] == "field-engineer"
    assert submission["state_assertion_id"] is not None

    field_candidate_id = submission["created_fact_candidate_id"]
    candidates = await _candidates(client, organization_id, project["id"])
    field_candidate = next(item for item in candidates if item["id"] == field_candidate_id)
    assert field_candidate["source_kind"] == "FIELD_VERIFICATION"
    assert field_candidate["document_id"] is None
    assert field_candidate["document_page_id"] is None
    assert field_candidate["verification_result_id"] == submission["verification"]["id"]
    assert field_candidate["review_state"] == "CONFIRMED"
    assert field_candidate["reviewed_value"] == "AZM 161"
    assert field_candidate["confidence"] == 1.0
    assert field_candidate["extraction_method"] == "field_verification"
    assert field_candidate["extraction_version"] == "v1"
    assert field_candidate["effective_date"] == submission["verification"]["verified_at"][:10]

    task_after = await client.get(
        f"/api/v1/verification-tasks/{task['id']}",
        headers={"X-Organization-Id": organization_id},
    )
    assert task_after.status_code == 200
    assert task_after.json()["status"] == "RESOLVED"
    assert task_after.json()["resolution_value"] == "AZM 161"

    result_response = await client.get(
        f"/api/v1/verification-tasks/{task['id']}/result",
        headers={"X-Organization-Id": organization_id},
    )
    assert result_response.status_code == 200
    assert result_response.json()["id"] == submission["verification"]["id"]

    assertions = (
        await client.get(
            f"/api/v1/projects/{project['id']}/state-assertions",
            headers={"X-Organization-Id": organization_id},
        )
    ).json()
    guard_state = next(
        item
        for item in assertions
        if item["fact_key"] == "safety.guard_switch.model"
    )
    assert guard_state["status"] == "DERIVED"
    assert guard_state["value"] == "AZM 161"

    detail = await client.get(
        f"/api/v1/state-assertions/{guard_state['id']}",
        headers={"X-Organization-Id": organization_id},
    )
    relationships = {
        item["fact_candidate_id"]: item["relationship"]
        for item in detail.json()["evidence"]
    }
    assert relationships[field_candidate_id] == "SUPPORTS"
    assert relationships[ambiguous["id"]] == "SUPERSEDED"

    duplicate = await client.post(
        f"/api/v1/verification-tasks/{task['id']}/verify",
        headers={
            "X-Organization-Id": organization_id,
            "X-Reviewer-Id": "field-engineer",
        },
        json={"observed_value": "AZM 161"},
    )
    assert duplicate.status_code == 409

    other_org = str(uuid.uuid4())
    hidden_task = await client.get(
        f"/api/v1/verification-tasks/{task['id']}",
        headers={"X-Organization-Id": other_org},
    )
    assert hidden_task.status_code == 404
    hidden_result = await client.get(
        f"/api/v1/verification-tasks/{task['id']}/result",
        headers={"X-Organization-Id": other_org},
    )
    assert hidden_result.status_code == 404


async def test_field_verification_resolves_undated_plc_conflict(
    client: AsyncClient,
) -> None:
    organization_id = str(uuid.uuid4())
    project, machine = await _create_project_and_machine(client, organization_id)

    for filename, plc in [
        ("plc_old.pdf", "Siemens S7-300"),
        ("plc_other.pdf", "Siemens S7-1500"),
    ]:
        await _upload_parse_extract(
            client,
            organization_id,
            project["id"],
            machine["id"],
            filename,
            make_text_pdf(
                [
                    (
                        "CONTROL INVENTORY\n"
                        "Machine: CV-204\n"
                        f"PLC platform: {plc}"
                    )
                ]
            ),
        )

    candidates = await _candidates(client, organization_id, project["id"])
    plc_candidates = [
        item for item in candidates if item["fact_key"] == "plc.platform"
    ]
    assert len(plc_candidates) == 2
    for candidate in plc_candidates:
        await _confirm(client, organization_id, candidate["id"])

    reconcile = await client.post(
        f"/api/v1/projects/{project['id']}/reconcile",
        headers={"X-Organization-Id": organization_id},
    )
    assert reconcile.status_code == 200

    tasks = (
        await client.get(
            f"/api/v1/projects/{project['id']}/verification-tasks",
            headers={"X-Organization-Id": organization_id},
        )
    ).json()
    task = next(
        item
        for item in tasks
        if item["reason_code"] == "CONFLICTING_REVIEWED_VALUES"
        and item["status"] == "OPEN"
    )

    submitted = await client.post(
        f"/api/v1/verification-tasks/{task['id']}/verify",
        headers={
            "X-Organization-Id": organization_id,
            "X-Reviewer-Id": "site-engineer",
        },
        json={"observed_value": "Siemens S7-1500"},
    )
    assert submitted.status_code == 200

    assertions = (
        await client.get(
            f"/api/v1/projects/{project['id']}/state-assertions",
            headers={"X-Organization-Id": organization_id},
        )
    ).json()
    plc_state = next(item for item in assertions if item["fact_key"] == "plc.platform")
    assert plc_state["status"] == "DERIVED"
    assert plc_state["value"] == "Siemens S7-1500"

    field_candidate_id = submitted.json()["created_fact_candidate_id"]
    detail = (
        await client.get(
            f"/api/v1/state-assertions/{plc_state['id']}",
            headers={"X-Organization-Id": organization_id},
        )
    ).json()
    relationships = {
        item["fact_candidate_id"]: item["relationship"]
        for item in detail["evidence"]
    }
    assert relationships[field_candidate_id] == "SUPPORTS"
    assert all(
        relationships[candidate["id"]] == "SUPERSEDED"
        for candidate in plc_candidates
    )


async def test_missing_document_task_cannot_be_field_verified(
    client: AsyncClient,
    tmp_path,
) -> None:
    organization_id = str(uuid.uuid4())
    project, machine = await _create_project_and_machine(client, organization_id)
    pack = tmp_path / "golden_missing_doc"
    generate_pack(pack)

    await _upload_parse_extract(
        client,
        organization_id,
        project["id"],
        machine["id"],
        "04_safety_modification_2022.pdf",
        (pack / "04_safety_modification_2022.pdf").read_bytes(),
    )
    candidates = await _candidates(client, organization_id, project["id"])
    reference = next(
        item
        for item in candidates
        if item["fact_key"] == "evidence.reference.risk_assessment"
    )
    await _confirm(client, organization_id, reference["id"])

    await client.post(
        f"/api/v1/projects/{project['id']}/reconcile",
        headers={"X-Organization-Id": organization_id},
    )
    tasks = (
        await client.get(
            f"/api/v1/projects/{project['id']}/verification-tasks",
            headers={"X-Organization-Id": organization_id},
        )
    ).json()
    task = next(
        item
        for item in tasks
        if item["reason_code"] == "MISSING_REFERENCED_DOCUMENT"
    )

    response = await client.post(
        f"/api/v1/verification-tasks/{task['id']}/verify",
        headers={
            "X-Organization-Id": organization_id,
            "X-Reviewer-Id": "field-engineer",
        },
        json={"observed_value": "not available"},
    )
    assert response.status_code == 409
    assert "supplying the referenced document" in response.json()["detail"]
