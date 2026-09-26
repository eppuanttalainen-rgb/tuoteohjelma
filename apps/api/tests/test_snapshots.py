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
            "title": "CV-204 Snapshot Test",
            "customer_reference": "RETROFIT-001",
            "objective": "Freeze reviewed current state before retrofit design",
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
            "internal_asset_id": "LINE-2-CV-204",
            "machine_type": "belt_conveyor",
        },
    )
    assert machine_response.status_code == 201
    return project, machine_response.json()


async def _upload_parse_extract(
    client: AsyncClient,
    organization_id: str,
    project_id: str,
    machine_id: str,
    path: Path,
) -> dict:
    upload = await client.post(
        f"/api/v1/projects/{project_id}/documents",
        headers={"X-Organization-Id": organization_id},
        data={"machine_id": machine_id},
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
    return document


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
            "X-Reviewer-Id": "snapshot-test-engineer",
        },
        json={"action": "CONFIRMED"},
    )
    assert response.status_code == 200


async def test_immutable_snapshot_and_report(
    client: AsyncClient,
    tmp_path: Path,
) -> None:
    organization_id = str(uuid.uuid4())
    project, machine = await _create_project_and_machine(client, organization_id)
    pack = tmp_path / "golden_snapshot"
    manifest = generate_pack(pack)

    uploaded_documents = []
    for filename in [
        "01_oem_manual_2009.pdf",
        "02_motor_replacement_2021.pdf",
        "04_safety_modification_2022.pdf",
        "07_guard_switch_field_note.pdf",
    ]:
        uploaded_documents.append(
            await _upload_parse_extract(
                client,
                organization_id,
                project["id"],
                machine["id"],
                pack / filename,
            )
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

    for candidate in [
        original_11,
        installed_15,
        risk_reference,
        ambiguous_guard,
    ]:
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
    guard_task = next(
        task
        for task in tasks
        if task["reason_code"] == "AMBIGUOUS_REVIEWED_VALUE"
    )
    assert any(
        task["reason_code"] == "MISSING_REFERENCED_DOCUMENT"
        and task["status"] == "OPEN"
        for task in tasks
    )

    field_verify = await client.post(
        f"/api/v1/verification-tasks/{guard_task['id']}/verify",
        headers={
            "X-Organization-Id": organization_id,
            "X-Reviewer-Id": "field-engineer",
        },
        json={
            "observed_value": "AZM 161",
            "note": "Verified from installed label.",
        },
    )
    assert field_verify.status_code == 200

    snapshot_response = await client.post(
        f"/api/v1/machines/{machine['id']}/snapshots",
        headers={
            "X-Organization-Id": organization_id,
            "X-Reviewer-Id": "snapshot-engineer",
        },
    )
    assert snapshot_response.status_code == 200
    snapshot = snapshot_response.json()
    assert snapshot["status"] == "WITH_OPEN_ITEMS"
    assert snapshot["schema_version"] == "1.0"
    assert len(snapshot["state_hash"]) == 64

    payload = snapshot["payload"]
    motor = next(
        assertion
        for assertion in payload["state_assertions"]
        if assertion["fact_key"] == "motor.power_kw"
    )
    assert motor["value"] == 15
    assert motor["status"] == "DERIVED"
    assert motor["effective_date"] == "2021-06-14"
    assert any(
        evidence["relationship"] == "SUPERSEDED"
        and evidence["value"] == 11
        for evidence in motor["evidence"]
    )

    guard = next(
        assertion
        for assertion in payload["state_assertions"]
        if assertion["fact_key"] == "safety.guard_switch.model"
    )
    assert guard["value"] == "AZM 161"
    assert any(
        evidence["source_kind"] == "FIELD_VERIFICATION"
        and evidence["relationship"] == "SUPPORTS"
        for evidence in guard["evidence"]
    )

    assert any(
        task["reason_code"] == "MISSING_REFERENCED_DOCUMENT"
        and task["status"] == "OPEN"
        for task in payload["verification_tasks"]
    )

    payload_hashes = {item["filename"]: item["sha256"] for item in payload["documents"]}
    for document in uploaded_documents:
        assert payload_hashes[document["filename"]] == document["sha256"]

    assert payload_hashes["01_oem_manual_2009.pdf"] == manifest["files"][
        "01_oem_manual_2009.pdf"
    ]["sha256"]

    same_snapshot_response = await client.post(
        f"/api/v1/machines/{machine['id']}/snapshots",
        headers={
            "X-Organization-Id": organization_id,
            "X-Reviewer-Id": "another-engineer",
        },
    )
    assert same_snapshot_response.status_code == 200
    same_snapshot = same_snapshot_response.json()
    assert same_snapshot["id"] == snapshot["id"]
    assert same_snapshot["state_hash"] == snapshot["state_hash"]
    assert same_snapshot["created_by"] == "snapshot-engineer"

    report_response = await client.get(
        f"/api/v1/snapshots/{snapshot['id']}/report",
        headers={"X-Organization-Id": organization_id},
    )
    assert report_response.status_code == 200
    assert report_response.headers["content-type"].startswith("text/html")
    first_report = report_response.text
    assert "15 kW" in first_report
    assert "11 kW" in first_report
    assert "AZM 161" in first_report
    assert "RA-2022-17" in first_report
    assert snapshot["state_hash"] in first_report
    assert "not a compliance certificate" in first_report.lower()
    assert "ACS580" not in first_report

    await _upload_parse_extract(
        client,
        organization_id,
        project["id"],
        machine["id"],
        pack / "03_drive_replacement_2021.pdf",
    )
    candidates = await _candidates(client, organization_id, project["id"])
    drive_family = next(
        item
        for item in candidates
        if item["fact_key"] == "drive.family"
        and item["normalized_value"] == "ACS580"
    )
    await _confirm(client, organization_id, drive_family["id"])

    live_reconcile = await client.post(
        f"/api/v1/projects/{project['id']}/reconcile",
        headers={"X-Organization-Id": organization_id},
    )
    assert live_reconcile.status_code == 200

    new_snapshot_response = await client.post(
        f"/api/v1/machines/{machine['id']}/snapshots",
        headers={
            "X-Organization-Id": organization_id,
            "X-Reviewer-Id": "snapshot-engineer",
        },
    )
    assert new_snapshot_response.status_code == 200
    new_snapshot = new_snapshot_response.json()
    assert new_snapshot["id"] != snapshot["id"]
    assert new_snapshot["state_hash"] != snapshot["state_hash"]
    assert any(
        assertion["fact_key"] == "drive.family"
        and assertion["value"] == "ACS580"
        for assertion in new_snapshot["payload"]["state_assertions"]
    )

    old_report_again = await client.get(
        f"/api/v1/snapshots/{snapshot['id']}/report",
        headers={"X-Organization-Id": organization_id},
    )
    assert old_report_again.status_code == 200
    assert old_report_again.text == first_report
    assert "ACS580" not in old_report_again.text

    new_report = await client.get(
        f"/api/v1/snapshots/{new_snapshot['id']}/report",
        headers={"X-Organization-Id": organization_id},
    )
    assert new_report.status_code == 200
    assert "ACS580" in new_report.text

    snapshots_response = await client.get(
        f"/api/v1/machines/{machine['id']}/snapshots",
        headers={"X-Organization-Id": organization_id},
    )
    assert snapshots_response.status_code == 200
    assert len(snapshots_response.json()) == 2

    hidden_snapshot = await client.get(
        f"/api/v1/snapshots/{snapshot['id']}",
        headers={"X-Organization-Id": str(uuid.uuid4())},
    )
    assert hidden_snapshot.status_code == 404

    hidden_report = await client.get(
        f"/api/v1/snapshots/{snapshot['id']}/report",
        headers={"X-Organization-Id": str(uuid.uuid4())},
    )
    assert hidden_report.status_code == 404


async def test_snapshot_requires_reconciled_state(client: AsyncClient) -> None:
    organization_id = str(uuid.uuid4())
    _, machine = await _create_project_and_machine(client, organization_id)

    response = await client.post(
        f"/api/v1/machines/{machine['id']}/snapshots",
        headers={
            "X-Organization-Id": organization_id,
            "X-Reviewer-Id": "snapshot-engineer",
        },
    )
    assert response.status_code == 409
    assert "Reconcile reviewed facts" in response.json()["detail"]
