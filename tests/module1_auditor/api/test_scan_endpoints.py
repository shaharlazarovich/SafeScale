"""API tests for scan management endpoints."""

import uuid

import pytest
from httpx import AsyncClient


async def _create_test_account(client: AsyncClient, account_id: str = "999999999999") -> str:
    """Helper to create a test account and return its internal ID."""
    payload = {
        "account_id": account_id,
        "account_name": f"Test-{account_id}",
        "role_arn": f"arn:aws:iam::{account_id}:role/SafeScaleDiscovery",
        "external_id": f"safescale-ext-{account_id}",
    }
    resp = await client.post("/api/accounts", json=payload)
    assert resp.status_code == 201
    return resp.json()["id"]


@pytest.mark.api
class TestStartScan:
    async def test_start_scan(self, client: AsyncClient):
        account_uuid = await _create_test_account(client, "500000000001")

        response = await client.post("/api/scans", json={"account_id": account_uuid})
        assert response.status_code == 201
        data = response.json()
        assert data["status"] == "pending"
        assert data["account_id"] == account_uuid
        assert "id" in data
        assert "created_at" in data

    async def test_start_scan_invalid_account(self, client: AsyncClient):
        fake_id = str(uuid.uuid4())
        response = await client.post("/api/scans", json={"account_id": fake_id})
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()


@pytest.mark.api
class TestListScans:
    async def test_list_scans(self, client: AsyncClient):
        response = await client.get("/api/scans")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    async def test_list_scans_filter_by_account(self, client: AsyncClient):
        account_uuid = await _create_test_account(client, "500000000002")
        await client.post("/api/scans", json={"account_id": account_uuid})

        response = await client.get(f"/api/scans?account_id={account_uuid}")
        assert response.status_code == 200
        data = response.json()
        assert all(s["account_id"] == account_uuid for s in data)


@pytest.mark.api
class TestGetScan:
    async def test_get_scan(self, client: AsyncClient):
        account_uuid = await _create_test_account(client, "500000000003")
        create_resp = await client.post("/api/scans", json={"account_id": account_uuid})
        scan_id = create_resp.json()["id"]

        response = await client.get(f"/api/scans/{scan_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == scan_id
        assert "status" in data
        assert "progress" in data

    async def test_get_scan_not_found(self, client: AsyncClient):
        fake_id = str(uuid.uuid4())
        response = await client.get(f"/api/scans/{fake_id}")
        assert response.status_code == 404


@pytest.mark.api
class TestGetScanResources:
    async def test_get_scan_resources(self, client: AsyncClient):
        account_uuid = await _create_test_account(client, "500000000004")
        create_resp = await client.post("/api/scans", json={"account_id": account_uuid})
        scan_id = create_resp.json()["id"]

        response = await client.get(f"/api/scans/{scan_id}/resources")
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "total" in data
        assert isinstance(data["items"], list)

    async def test_get_scan_resources_pagination(self, client: AsyncClient):
        account_uuid = await _create_test_account(client, "500000000005")
        create_resp = await client.post("/api/scans", json={"account_id": account_uuid})
        scan_id = create_resp.json()["id"]

        response = await client.get(f"/api/scans/{scan_id}/resources?limit=10&offset=0")
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "total" in data
        assert "limit" in data
        assert "offset" in data


@pytest.mark.api
class TestGetScanLog:
    async def test_get_scan_log(self, client: AsyncClient):
        account_uuid = await _create_test_account(client, "500000000006")
        create_resp = await client.post("/api/scans", json={"account_id": account_uuid})
        scan_id = create_resp.json()["id"]

        response = await client.get(f"/api/scans/{scan_id}/log")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    async def test_get_scan_log_filter_by_phase(self, client: AsyncClient):
        account_uuid = await _create_test_account(client, "500000000007")
        create_resp = await client.post("/api/scans", json={"account_id": account_uuid})
        scan_id = create_resp.json()["id"]

        response = await client.get(f"/api/scans/{scan_id}/log?phase=enumeration")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    async def test_get_scan_log_filter_by_severity(self, client: AsyncClient):
        account_uuid = await _create_test_account(client, "500000000008")
        create_resp = await client.post("/api/scans", json={"account_id": account_uuid})
        scan_id = create_resp.json()["id"]

        response = await client.get(f"/api/scans/{scan_id}/log?severity=error")
        assert response.status_code == 200
        assert isinstance(response.json(), list)
