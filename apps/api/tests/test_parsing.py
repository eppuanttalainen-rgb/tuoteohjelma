import hashlib
import uuid

from httpx import AsyncClient

from tests.pdf_factory import make_text_pdf


async def _create_project(client: AsyncClient, organization_id: str) -> dict:
    response = await client.post(
        "/api/v1/projects",
        headers={"X-Organization-Id": organization_id},
        json={"title": "CV-204 Parsing Test"},
    )
    assert response.status_code == 201
    return response.json()


async def _upload_pdf(
    client: AsyncClient,
    organization_id: str,
    project_id: str,
    payload: bytes,
    filename: str = "synthetic.pdf",
) -> dict:
    response = await client.post(
        f"/api/v1/projects/{project_id}/documents",
        headers={"X-Organization-Id": organization_id},
        files={"file": (filename, payload, "application/pdf")},
    )
    assert response.status_code == 201
    return response.json()


async def test_parse_document_persists_page_level_provenance(
    client: AsyncClient,
) -> None:
    organization_id = str(uuid.uuid4())
    project = await _create_project(client, organization_id)
    pdf = make_text_pdf(
        [
            "CV-204 ORIGINAL MANUAL\nOriginal motor power: 11 kW",
            "DRIVE INFORMATION\nReplacement drive: ABB ACS580",
        ]
    )
    document = await _upload_pdf(
        client,
        organization_id,
        project["id"],
        pdf,
        "CV-204_Original_Manual.pdf",
    )

    parse_response = await client.post(
        f"/api/v1/documents/{document['id']}/parse",
        headers={"X-Organization-Id": organization_id},
    )
    assert parse_response.status_code == 200

    parse_result = parse_response.json()
    assert parse_result["document_id"] == document["id"]
    assert parse_result["processing_status"] == "PARSED"
    assert parse_result["page_count"] == 2
    assert parse_result["parser_name"] == "pypdf"
    assert parse_result["parser_version"] == "6.19.0"

    pages_response = await client.get(
        f"/api/v1/documents/{document['id']}/pages",
        headers={"X-Organization-Id": organization_id},
    )
    assert pages_response.status_code == 200
    pages = pages_response.json()

    assert [page["page_number"] for page in pages] == [1, 2]
    assert "Original motor power: 11 kW" in pages[0]["text"]
    assert "Replacement drive: ABB ACS580" in pages[1]["text"]

    for page in pages:
        assert page["text_sha256"] == hashlib.sha256(
            page["text"].encode("utf-8")
        ).hexdigest()
        assert page["parser_name"] == "pypdf"
        assert page["parser_version"] == "6.19.0"

    original_hashes = [page["text_sha256"] for page in pages]
    original_ids = [page["id"] for page in pages]

    reparse = await client.post(
        f"/api/v1/documents/{document['id']}/parse",
        headers={"X-Organization-Id": organization_id},
    )
    assert reparse.status_code == 200

    reparsed_pages = (
        await client.get(
            f"/api/v1/documents/{document['id']}/pages",
            headers={"X-Organization-Id": organization_id},
        )
    ).json()

    assert len(reparsed_pages) == 2
    assert [page["id"] for page in reparsed_pages] == original_ids
    assert [page["text_sha256"] for page in reparsed_pages] == original_hashes


async def test_parse_failure_is_visible_on_document(client: AsyncClient) -> None:
    organization_id = str(uuid.uuid4())
    project = await _create_project(client, organization_id)
    malformed_pdf = b"%PDF-this-is-not-a-structurally-valid-pdf"

    document = await _upload_pdf(
        client,
        organization_id,
        project["id"],
        malformed_pdf,
        "broken.pdf",
    )

    parse_response = await client.post(
        f"/api/v1/documents/{document['id']}/parse",
        headers={"X-Organization-Id": organization_id},
    )
    assert parse_response.status_code == 422

    document_response = await client.get(
        f"/api/v1/documents/{document['id']}",
        headers={"X-Organization-Id": organization_id},
    )
    assert document_response.status_code == 200
    assert document_response.json()["processing_status"] == "PARSE_FAILED"

    pages_response = await client.get(
        f"/api/v1/documents/{document['id']}/pages",
        headers={"X-Organization-Id": organization_id},
    )
    assert pages_response.status_code == 200
    assert pages_response.json() == []


async def test_parsed_pages_are_tenant_scoped(client: AsyncClient) -> None:
    organization_a = str(uuid.uuid4())
    organization_b = str(uuid.uuid4())
    project = await _create_project(client, organization_a)
    document = await _upload_pdf(
        client,
        organization_a,
        project["id"],
        make_text_pdf(["Tenant A only"]),
    )

    denied_parse = await client.post(
        f"/api/v1/documents/{document['id']}/parse",
        headers={"X-Organization-Id": organization_b},
    )
    assert denied_parse.status_code == 404

    allowed_parse = await client.post(
        f"/api/v1/documents/{document['id']}/parse",
        headers={"X-Organization-Id": organization_a},
    )
    assert allowed_parse.status_code == 200

    denied_pages = await client.get(
        f"/api/v1/documents/{document['id']}/pages",
        headers={"X-Organization-Id": organization_b},
    )
    assert denied_pages.status_code == 404
