import uuid

from httpx import AsyncClient


async def test_project_and_machine_are_tenant_scoped(client: AsyncClient) -> None:
    organization_a = str(uuid.uuid4())
    organization_b = str(uuid.uuid4())

    project_response = await client.post(
        "/api/v1/projects",
        headers={"X-Organization-Id": organization_a},
        json={
            "title": "CV-204 Retrofit",
            "customer_reference": "P-001",
            "objective": "Reconstruct current state before retrofit",
            "jurisdiction": "EU",
        },
    )
    assert project_response.status_code == 201

    project = project_response.json()
    assert project["organization_id"] == organization_a
    assert project["title"] == "CV-204 Retrofit"

    project_id = project["id"]

    hidden_from_other_tenant = await client.get(
        f"/api/v1/projects/{project_id}",
        headers={"X-Organization-Id": organization_b},
    )
    assert hidden_from_other_tenant.status_code == 404

    machine_response = await client.post(
        f"/api/v1/projects/{project_id}/machines",
        headers={"X-Organization-Id": organization_a},
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

    machine = machine_response.json()
    assert machine["organization_id"] == organization_a
    assert machine["project_id"] == project_id
    assert machine["model"] == "CV-204"

    machine_id = machine["id"]

    hidden_machine = await client.get(
        f"/api/v1/machines/{machine_id}",
        headers={"X-Organization-Id": organization_b},
    )
    assert hidden_machine.status_code == 404

    visible_machine = await client.get(
        f"/api/v1/machines/{machine_id}",
        headers={"X-Organization-Id": organization_a},
    )
    assert visible_machine.status_code == 200
    assert visible_machine.json()["serial_number"] == "NHS-CV204-09117"


async def test_project_listing_is_tenant_scoped(client: AsyncClient) -> None:
    organization_a = str(uuid.uuid4())
    organization_b = str(uuid.uuid4())

    await client.post(
        "/api/v1/projects",
        headers={"X-Organization-Id": organization_a},
        json={"title": "Tenant A Project"},
    )

    await client.post(
        "/api/v1/projects",
        headers={"X-Organization-Id": organization_b},
        json={"title": "Tenant B Project"},
    )

    response_a = await client.get(
        "/api/v1/projects",
        headers={"X-Organization-Id": organization_a},
    )
    response_b = await client.get(
        "/api/v1/projects",
        headers={"X-Organization-Id": organization_b},
    )

    assert response_a.status_code == 200
    assert response_b.status_code == 200
    assert [project["title"] for project in response_a.json()] == ["Tenant A Project"]
    assert [project["title"] for project in response_b.json()] == ["Tenant B Project"]
