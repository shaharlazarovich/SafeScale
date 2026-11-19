"""API tests for AWS account management endpoints."""

import pytest
from httpx import AsyncClient


@pytest.mark.api
class TestCreateAccount:
    async def test_create_account(self, client: AsyncClient):
        payload = {
            "account_id": "123456789012",
            "account_name": "Production",
            "role_arn": "arn:aws:iam::123456789012:role/SafeScaleDiscovery",
            "external_id": "safescale-ext-abc123",
            "regions": ["us-east-1", "us-west-2"],
        }
        response = await client.post("/api/accounts", json=payload)
        assert response.status_code == 201
        data = response.json()
        assert data["account_id"] == "123456789012"
        assert data["account_name"] == "Production"
        assert data["status"] == "connected"
        assert "id" in data

    async def test_create_account_duplicate(self, client: AsyncClient):
        payload = {
            "account_id": "111111111111",
            "account_name": "Staging",
            "role_arn": "arn:aws:iam::111111111111:role/SafeScaleDiscovery",
            "external_id": "safescale-ext-def456",
        }
        response = await client.post("/api/accounts", json=payload)
        assert response.status_code == 201

        response = await client.post("/api/accounts", json=payload)
        assert response.status_code == 409
        assert "already exists" in response.json()["detail"].lower()

    async def test_create_account_invalid_arn(self, client: AsyncClient):
        payload = {
            "account_id": "222222222222",
            "account_name": "Bad ARN",
            "role_arn": "not-a-valid-arn",
            "external_id": "safescale-ext-ghi789",
        }
        response = await client.post("/api/accounts", json=payload)
        assert response.status_code == 422


@pytest.mark.api
class TestListAccounts:
    async def test_list_accounts(self, client: AsyncClient):
        response = await client.get("/api/accounts")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)


@pytest.mark.api
class TestGetAccount:
    async def test_get_account(self, client: AsyncClient):
        create_payload = {
            "account_id": "333333333333",
            "account_name": "Dev",
            "role_arn": "arn:aws:iam::333333333333:role/SafeScaleDiscovery",
            "external_id": "safescale-ext-jkl012",
        }
        create_resp = await client.post("/api/accounts", json=create_payload)
        assert create_resp.status_code == 201
        account_id = create_resp.json()["id"]

        response = await client.get(f"/api/accounts/{account_id}")
        assert response.status_code == 200
        assert response.json()["account_id"] == "333333333333"

    async def test_get_account_not_found(self, client: AsyncClient):
        import uuid

        fake_id = str(uuid.uuid4())
        response = await client.get(f"/api/accounts/{fake_id}")
        assert response.status_code == 404


@pytest.mark.api
class TestDeleteAccount:
    async def test_delete_account(self, client: AsyncClient):
        create_payload = {
            "account_id": "444444444444",
            "account_name": "Sandbox",
            "role_arn": "arn:aws:iam::444444444444:role/SafeScaleDiscovery",
            "external_id": "safescale-ext-mno345",
        }
        create_resp = await client.post("/api/accounts", json=create_payload)
        assert create_resp.status_code == 201
        account_id = create_resp.json()["id"]

        response = await client.delete(f"/api/accounts/{account_id}")
        assert response.status_code == 204

        get_resp = await client.get(f"/api/accounts/{account_id}")
        assert get_resp.status_code == 404
