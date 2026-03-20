"""Tests for external apps caching behavior."""

from typing import Any

from fastapi import status
from starlette.testclient import TestClient

from tests.conftest import create_auth_headers
from tests.helpers.tenant import create_tenant_for_user

ENDPOINT_EXTERNAL_APPS = "/api/v1/platform-service/tenants/{tenant_id}/external-apps"
ENDPOINT_EXTERNAL_APP_DETAIL = "/api/v1/platform-service/tenants/{tenant_id}/external-apps/{external_app_id}"


def create_external_app(test_client: TestClient, tenant_id: str, headers: dict, name: str = "Test App") -> str:
    """Helper function to create an external app and return its ID."""
    response = test_client.post(
        ENDPOINT_EXTERNAL_APPS.format(tenant_id=tenant_id),
        json={"name": name, "description": f"Description for {name}", "url": "https://example.com"},
        headers=headers,
    )
    assert response.status_code == status.HTTP_201_CREATED
    return response.json()["id"]


class TestExternalAppCaching:
    """Test suite for external app caching behavior with X-Use-Cache enabled."""

    def test_list_cached_on_second_call(self, test_client: TestClient, fake_redis_client: Any) -> None:
        """Test that list results are cached on second call."""
        user_token = test_client.create_test_user("ea-cache-1", "EA Cache 1")
        headers = create_auth_headers(user_token)
        tenant_id = create_tenant_for_user(test_client, user_token)

        create_external_app(test_client, tenant_id, headers, "Cached App")

        response1 = test_client.get(ENDPOINT_EXTERNAL_APPS.format(tenant_id=tenant_id), headers=headers)
        assert response1.status_code == status.HTTP_200_OK
        assert len(response1.json()) == 1

        response2 = test_client.get(ENDPOINT_EXTERNAL_APPS.format(tenant_id=tenant_id), headers=headers)
        assert response2.status_code == status.HTTP_200_OK
        assert len(response2.json()) == 1

    def test_detail_cached_on_second_call(self, test_client: TestClient, fake_redis_client: Any) -> None:
        """Test that detail results are cached on second call."""
        user_token = test_client.create_test_user("ea-cache-2", "EA Cache 2")
        headers = create_auth_headers(user_token)
        tenant_id = create_tenant_for_user(test_client, user_token)

        app_id = create_external_app(test_client, tenant_id, headers, "Cached Detail")

        response1 = test_client.get(
            ENDPOINT_EXTERNAL_APP_DETAIL.format(tenant_id=tenant_id, external_app_id=app_id), headers=headers
        )
        assert response1.status_code == status.HTTP_200_OK

        response2 = test_client.get(
            ENDPOINT_EXTERNAL_APP_DETAIL.format(tenant_id=tenant_id, external_app_id=app_id), headers=headers
        )
        assert response2.status_code == status.HTTP_200_OK
        assert response2.json()["name"] == "Cached Detail"

    def test_create_invalidates_list_cache(self, test_client: TestClient, fake_redis_client: Any) -> None:
        """Test that creating an app invalidates the list cache."""
        user_token = test_client.create_test_user("ea-cache-3", "EA Cache 3")
        headers = create_auth_headers(user_token)
        tenant_id = create_tenant_for_user(test_client, user_token)

        response1 = test_client.get(ENDPOINT_EXTERNAL_APPS.format(tenant_id=tenant_id), headers=headers)
        assert response1.status_code == status.HTTP_200_OK
        assert len(response1.json()) == 0

        create_external_app(test_client, tenant_id, headers, "New App")

        response2 = test_client.get(ENDPOINT_EXTERNAL_APPS.format(tenant_id=tenant_id), headers=headers)
        assert response2.status_code == status.HTTP_200_OK
        assert len(response2.json()) == 1

    def test_update_invalidates_caches(self, test_client: TestClient, fake_redis_client: Any) -> None:
        """Test that updating an app invalidates both list and detail caches."""
        user_token = test_client.create_test_user("ea-cache-4", "EA Cache 4")
        headers = create_auth_headers(user_token)
        tenant_id = create_tenant_for_user(test_client, user_token)

        app_id = create_external_app(test_client, tenant_id, headers, "Original Name")

        test_client.get(
            ENDPOINT_EXTERNAL_APP_DETAIL.format(tenant_id=tenant_id, external_app_id=app_id), headers=headers
        )

        test_client.patch(
            ENDPOINT_EXTERNAL_APP_DETAIL.format(tenant_id=tenant_id, external_app_id=app_id),
            json={"name": "Updated Name"},
            headers=headers,
        )

        response = test_client.get(
            ENDPOINT_EXTERNAL_APP_DETAIL.format(tenant_id=tenant_id, external_app_id=app_id), headers=headers
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["name"] == "Updated Name"

    def test_delete_invalidates_caches(self, test_client: TestClient, fake_redis_client: Any) -> None:
        """Test that deleting an app invalidates caches."""
        user_token = test_client.create_test_user("ea-cache-5", "EA Cache 5")
        headers = create_auth_headers(user_token)
        tenant_id = create_tenant_for_user(test_client, user_token)

        app_id = create_external_app(test_client, tenant_id, headers, "To Delete")

        test_client.get(ENDPOINT_EXTERNAL_APPS.format(tenant_id=tenant_id), headers=headers)
        test_client.get(
            ENDPOINT_EXTERNAL_APP_DETAIL.format(tenant_id=tenant_id, external_app_id=app_id), headers=headers
        )

        test_client.request(
            "DELETE",
            ENDPOINT_EXTERNAL_APP_DETAIL.format(tenant_id=tenant_id, external_app_id=app_id),
            headers=headers,
        )

        response = test_client.get(ENDPOINT_EXTERNAL_APPS.format(tenant_id=tenant_id), headers=headers)
        assert response.status_code == status.HTTP_200_OK
        assert len(response.json()) == 0

    def test_name_filter_bypasses_cache(self, test_client: TestClient, fake_redis_client: Any) -> None:
        """Test that name filter bypasses caching."""
        user_token = test_client.create_test_user("ea-cache-6", "EA Cache 6")
        headers = create_auth_headers(user_token)
        tenant_id = create_tenant_for_user(test_client, user_token)

        create_external_app(test_client, tenant_id, headers, "Alpha App")
        create_external_app(test_client, tenant_id, headers, "Beta App")

        response = test_client.get(f"{ENDPOINT_EXTERNAL_APPS.format(tenant_id=tenant_id)}?name=Alpha", headers=headers)
        assert response.status_code == status.HTTP_200_OK
        assert len(response.json()) == 1
        assert response.json()[0]["name"] == "Alpha App"
