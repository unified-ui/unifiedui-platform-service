"""Tests for external apps API endpoints."""

from typing import Any

from fastapi import status
from starlette.testclient import TestClient

from tests.conftest import create_auth_headers
from tests.helpers.tenant import create_tenant_for_user

ENDPOINT_EXTERNAL_APPS = "/api/v1/platform-service/tenants/{tenant_id}/external-apps"
ENDPOINT_EXTERNAL_APP_DETAIL = "/api/v1/platform-service/tenants/{tenant_id}/external-apps/{external_app_id}"

NON_EXISTENT_ID = "non-existent-id"


def create_external_app(
    test_client: TestClient, tenant_id: str, headers: dict, name: str = "Test App", url: str = "https://example.com"
) -> str:
    """Helper function to create an external app and return its ID."""
    response = test_client.post(
        ENDPOINT_EXTERNAL_APPS.format(tenant_id=tenant_id),
        json={
            "name": name,
            "description": f"Description for {name}",
            "config": {"mode": "url", "url": url, "params": {}},
        },
        headers=headers,
    )
    assert response.status_code == status.HTTP_201_CREATED
    return response.json()["id"]


class TestExternalAppRoutes:
    """Test suite for external app API routes."""

    def test_create_external_app_success(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test successful external app creation."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)

        app_data = {
            "name": "Test External App",
            "description": "A test external app",
            "config": {"mode": "url", "url": "https://example.com/app", "params": {}},
            "image_url": "https://example.com/image.png",
        }

        response = test_client.post(ENDPOINT_EXTERNAL_APPS.format(tenant_id=tenant_id), json=app_data, headers=headers)

        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()

        assert data["name"] == app_data["name"]
        assert data["description"] == app_data["description"]
        assert data["config"]["mode"] == "url"
        assert data["config"]["url"] == "https://example.com/app"
        assert data["image_url"] == app_data["image_url"]
        assert "id" in data
        assert data["tenant_id"] == tenant_id
        assert "created_at" in data
        assert "updated_at" in data
        assert data["created_by"] == test_user_token.get_id()

    def test_create_external_app_minimal(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test external app creation with minimal fields."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)

        app_data = {"name": "Minimal App", "config": {"mode": "url", "url": "https://example.com", "params": {}}}

        response = test_client.post(ENDPOINT_EXTERNAL_APPS.format(tenant_id=tenant_id), json=app_data, headers=headers)

        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["name"] == "Minimal App"
        assert data["description"] is None
        assert data["image_url"] is None

    def test_create_external_app_missing_name(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test external app creation with missing name."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)

        response = test_client.post(
            ENDPOINT_EXTERNAL_APPS.format(tenant_id=tenant_id),
            json={"config": {"mode": "url", "url": "https://example.com", "params": {}}},
            headers=headers,
        )
        assert response.status_code == 422

    def test_create_external_app_missing_url(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test external app creation with missing config."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)

        response = test_client.post(
            ENDPOINT_EXTERNAL_APPS.format(tenant_id=tenant_id),
            json={"name": "Test App"},
            headers=headers,
        )
        assert response.status_code == 422

    def test_create_external_app_empty_name(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test external app creation with empty name."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)

        response = test_client.post(
            ENDPOINT_EXTERNAL_APPS.format(tenant_id=tenant_id),
            json={"name": "", "config": {"mode": "url", "url": "https://example.com", "params": {}}},
            headers=headers,
        )
        assert response.status_code == 422

    def test_create_external_app_empty_body(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test external app creation with empty body."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)

        response = test_client.post(ENDPOINT_EXTERNAL_APPS.format(tenant_id=tenant_id), json={}, headers=headers)
        assert response.status_code == 422

    def test_get_external_app_success(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test successful external app retrieval."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)

        app_id = create_external_app(test_client, tenant_id, headers)

        response = test_client.get(
            ENDPOINT_EXTERNAL_APP_DETAIL.format(tenant_id=tenant_id, external_app_id=app_id), headers=headers
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["id"] == app_id
        assert data["name"] == "Test App"

    def test_get_external_app_not_found(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test external app retrieval with non-existent ID."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)

        response = test_client.get(
            ENDPOINT_EXTERNAL_APP_DETAIL.format(tenant_id=tenant_id, external_app_id=NON_EXISTENT_ID), headers=headers
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_list_external_apps_empty(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test listing external apps when none exist."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)

        response = test_client.get(ENDPOINT_EXTERNAL_APPS.format(tenant_id=tenant_id), headers=headers)

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == []

    def test_list_external_apps_with_data(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test listing external apps with existing data."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)

        create_external_app(test_client, tenant_id, headers, "App 1")
        create_external_app(test_client, tenant_id, headers, "App 2")

        response = test_client.get(ENDPOINT_EXTERNAL_APPS.format(tenant_id=tenant_id), headers=headers)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data) == 2
        names = [app["name"] for app in data]
        assert "App 1" in names
        assert "App 2" in names

    def test_list_external_apps_with_pagination(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test listing external apps with pagination."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)

        for i in range(5):
            create_external_app(test_client, tenant_id, headers, f"App {i}")

        response = test_client.get(f"{ENDPOINT_EXTERNAL_APPS.format(tenant_id=tenant_id)}?limit=3", headers=headers)
        assert response.status_code == status.HTTP_200_OK
        assert len(response.json()) == 3

        response = test_client.get(
            f"{ENDPOINT_EXTERNAL_APPS.format(tenant_id=tenant_id)}?skip=2&limit=2", headers=headers
        )
        assert response.status_code == status.HTTP_200_OK
        assert len(response.json()) == 2

    def test_list_external_apps_with_name_filter(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test listing external apps with name filter."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)

        create_external_app(test_client, tenant_id, headers, "Production App")
        create_external_app(test_client, tenant_id, headers, "Staging App")
        create_external_app(test_client, tenant_id, headers, "Other Tool")

        response = test_client.get(f"{ENDPOINT_EXTERNAL_APPS.format(tenant_id=tenant_id)}?name=App", headers=headers)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data) == 2

    def test_list_external_apps_with_ordering(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test listing external apps with ordering."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)

        create_external_app(test_client, tenant_id, headers, "Bravo App")
        create_external_app(test_client, tenant_id, headers, "Alpha App")
        create_external_app(test_client, tenant_id, headers, "Charlie App")

        response = test_client.get(
            f"{ENDPOINT_EXTERNAL_APPS.format(tenant_id=tenant_id)}?order_by=name&order_direction=asc", headers=headers
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        names = [app["name"] for app in data]
        assert names == sorted(names)

    def test_update_external_app_success(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test successful external app update."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)

        app_id = create_external_app(test_client, tenant_id, headers)

        response = test_client.patch(
            ENDPOINT_EXTERNAL_APP_DETAIL.format(tenant_id=tenant_id, external_app_id=app_id),
            json={
                "name": "Updated App",
                "config": {"mode": "url", "url": "https://updated.example.com", "params": {}},
            },
            headers=headers,
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["name"] == "Updated App"
        assert data["config"]["url"] == "https://updated.example.com"

    def test_update_external_app_partial(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test partial external app update."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)

        app_id = create_external_app(test_client, tenant_id, headers, "Original Name", "https://original.com")

        response = test_client.patch(
            ENDPOINT_EXTERNAL_APP_DETAIL.format(tenant_id=tenant_id, external_app_id=app_id),
            json={"name": "New Name"},
            headers=headers,
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["name"] == "New Name"
        assert data["config"]["url"] == "https://original.com"

    def test_update_external_app_not_found(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test updating a non-existent external app."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)

        response = test_client.patch(
            ENDPOINT_EXTERNAL_APP_DETAIL.format(tenant_id=tenant_id, external_app_id=NON_EXISTENT_ID),
            json={"name": "Updated"},
            headers=headers,
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_delete_external_app_success(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test successful external app deletion."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)

        app_id = create_external_app(test_client, tenant_id, headers)

        response = test_client.request(
            "DELETE", ENDPOINT_EXTERNAL_APP_DETAIL.format(tenant_id=tenant_id, external_app_id=app_id), headers=headers
        )
        assert response.status_code == status.HTTP_204_NO_CONTENT

        get_response = test_client.get(
            ENDPOINT_EXTERNAL_APP_DETAIL.format(tenant_id=tenant_id, external_app_id=app_id), headers=headers
        )
        assert get_response.status_code == status.HTTP_404_NOT_FOUND

    def test_delete_external_app_not_found(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test deleting a non-existent external app."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)

        response = test_client.request(
            "DELETE",
            ENDPOINT_EXTERNAL_APP_DETAIL.format(tenant_id=tenant_id, external_app_id=NON_EXISTENT_ID),
            headers=headers,
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_cross_tenant_isolation(self, test_client: TestClient) -> None:
        """Test that external apps are isolated between tenants."""
        user1_token = test_client.create_test_user("ea-user-1", "EA User 1")
        user2_token = test_client.create_test_user("ea-user-2", "EA User 2")
        tenant1_id = create_tenant_for_user(test_client, user1_token)
        tenant2_id = create_tenant_for_user(test_client, user2_token, "Tenant 2")
        headers1 = create_auth_headers(user1_token, use_cache=False)
        headers2 = create_auth_headers(user2_token, use_cache=False)

        app_id = create_external_app(test_client, tenant1_id, headers1, "Tenant 1 App")

        response = test_client.get(
            ENDPOINT_EXTERNAL_APP_DETAIL.format(tenant_id=tenant2_id, external_app_id=app_id), headers=headers2
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_unauthenticated_access_denied(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test that unauthenticated requests are denied."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)

        response = test_client.get(ENDPOINT_EXTERNAL_APPS.format(tenant_id=tenant_id))
        assert response.status_code in (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN)
