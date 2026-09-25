import hashlib
import uuid

from httpx import AsyncClient

PDF_BYTES = b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\n%%EOF\n"


async def _create_project(client: AsyncClient, organization_id: str) -> dict:
    response = await client.post(
        "/api/v1/projects",
        headers={"X-Organization-Id": organization_id},
        json={"title": "CV-204 Evidence Test"},
    )
    assert response.status_code == 201
    return response.json()


async def test_upload_inventory_and_duplicate_detection(client: AsyncClient) -> None:
    organization_id = str(uuid.uuid4())
    project = await _create_project(client, organization_id)

    machine_response = await client.post(
        f"/api/v1/projects/{project['id']}/machines",
        headers={"X-Organization-Id": organization_id},
        json={
            "manufacturer": "Northfield Handling Systems",
            "model": "CV-204",
            "serial_number": "NHS-CV204-09117",
        },
    )
    assert machine_response.status_code == 201
    machine_id = machine_response.json()["id"]

    upload = await client.post(
        f"/api/v1/projects/{project['id']}/documents",
        headers={"X-Organization-Id": organization_id},
        data={"machine_id": machine_id},
        files={"file": ("Original_Manual.pdf", PDF_BYTES, "application/pdf")},
    )
    assert upload.status_code == 201

    document = upload.json()
    assert document["filename"] == "Original_Manual.pdf"
    assert document["machine_id"] == machine_id
    assert document["processing_status"] == "STORED"
    assert document["sha256"] == hashlib.sha256(PDF_BYTES).hexdigest()
    assert document["size_bytes"] == len(PDF_BYTES)

    inventory = await client.get(
        f"/api/v1/projects/{project['id']}/documents",
        headers={"X-Organization-Id": organization_id},
    )
    assert inventory.status_code == 200
    assert [item["id"] for item in inventory.json()] == [document["id"]]

    duplicate = await client.post(
        f"/api/v1/projects/{project['id']}/documents",
        headers={"X-Organization-Id": organization_id},
        files={"file": ("Copy_of_Manual.pdf", PDF_BYTES, "application/pdf")},
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["detail"]["existing_document_id"] == document["id"]

    inventory_after_duplicate = await client.get(
        f"/api/v1/projects/{project['id']}/documents",
        headers={"X-Organization-Id": organization_id},
    )
    assert len(inventory_after_duplicate.json()) == 1


async def test_upload_rejects_non_pdf_and_fake_pdf(client: AsyncClient) -> None:
    organization_id = str(uuid.uuid4())
    project = await _create_project(client, organization_id)
    endpoint = f"/api/v1/projects/{project['id']}/documents"
    headers = {"X-Organization-Id": organization_id}

    wrong_content_type = await client.post(
        endpoint,
        headers=headers,
        files={"file": ("notes.txt", b"plain text", "text/plain")},
    )
    assert wrong_content_type.status_code == 415

    fake_pdf = await client.post(
        endpoint,
        headers=headers,
        files={"file": ("fake.pdf", b"not really a pdf", "application/pdf")},
    )
    assert fake_pdf.status_code == 415


async def test_document_inventory_is_tenant_scoped(client: AsyncClient) -> None:
    organization_a = str(uuid.uuid4())
    organization_b = str(uuid.uuid4())
    project = await _create_project(client, organization_a)

    upload = await client.post(
        f"/api/v1/projects/{project['id']}/documents",
        headers={"X-Organization-Id": organization_a},
        files={"file": ("manual.pdf", PDF_BYTES, "application/pdf")},
    )
    assert upload.status_code == 201

    hidden_inventory = await client.get(
        f"/api/v1/projects/{project['id']}/documents",
        headers={"X-Organization-Id": organization_b},
    )
    assert hidden_inventory.status_code == 404

    hidden_document = await client.get(
        f"/api/v1/documents/{upload.json()['id']}",
        headers={"X-Organization-Id": organization_b},
    )
    assert hidden_document.status_code == 404


async def test_upload_rejects_file_over_configured_limit(client: AsyncClient) -> None:
    organization_id = str(uuid.uuid4())
    project = await _create_project(client, organization_id)

    oversized_pdf = b"%PDF-" + (b"x" * 5000)
    response = await client.post(
        f"/api/v1/projects/{project['id']}/documents",
        headers={"X-Organization-Id": organization_id},
        files={"file": ("oversized.pdf", oversized_pdf, "application/pdf")},
    )

    assert response.status_code == 413
